# PYTHON_ARGCOMPLETE_OK

# Copyright (c) 2014 Yubico AB
# All rights reserved.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
# Additional permission under GNU GPL version 3 section 7
#
# If you modify this program, or any covered work, by linking or
# combining it with the OpenSSL project's OpenSSL library (or a
# modified version of that library), containing parts covered by the
# terms of the OpenSSL or SSLeay licenses, We grant you additional
# permission to convey the resulting work. Corresponding Source for a
# non-source form of such a combination shall include the source code
# for the parts of OpenSSL used as well as that of the covered work.

from __future__ import print_function

try:
    from configparser import ConfigParser
except ImportError:
    from ConfigParser import ConfigParser

from .. import __version__
from ..core.ccid import open_scard
from ..core.sqlite import open_sqlite
from ..core.utils import ALG_SHA1, ALG_SHA256, ALG_SHA512, TYPE_HOTP, TYPE_TOTP, parse_uri
from ..core.exc import NoSpaceError
from .keystore import CONFIG_HOME, get_keystore
from .controller import CliController
from time import time
from base64 import b32decode
import click
import os
import sys


def print_creds(results):
    if not results:
        click.echo('No credentials found.')
        return

    longest = max(len(r[0].name) for r in results)
    format_str = '{:<%d}  {:>10}' % longest
    for (cred, code) in results:
        if code is None:
            if cred.oath_type == TYPE_HOTP:
                code = '[HOTP credential]'
            elif cred.touch:
                code = '[Touch credential]'
        click.echo(format_str.format(cred.name, code))


CLICK_CONTEXT_SETTINGS = dict(
    help_option_names=['-h', '--help']
)


def print_version(ctx, param, value):
    if not value or ctx.resilient_parsing:
        return
    click.echo('yubioath {}'.format(__version__))
    ctx.exit()


@click.group(context_settings=CLICK_CONTEXT_SETTINGS)
@click.option('-v', '--version', is_flag=True, callback=print_version,
              expose_value=False, is_eager=True, help='Prints the version of '
              'the application and exits.')
@click.option('-b', '--backend', default=None, help='OATH storage backend to use')
@click.option('-r', '--reader', default='YubiKey', help='Name to match '
              'smartcard reader against (case insensitive).')
@click.option('-R', '--remember', is_flag=True, help='Remember any entered '
              'access key for later use.')
@click.pass_context
def cli(ctx, backend, reader, remember):
    """
    Read OATH one time passwords from a YubiKey.
    """
    parser = ConfigParser()
    parser.read([os.path.join(CONFIG_HOME, 'settings.ini')])
    if 'settings' in parser:
        ctx.obj['settings'] = parser['settings']
    else:
        ctx.obj['settings'] = {}
    if backend is None:
        backend = ctx.obj['settings'].get('backend', 'ccid')
    if backend == 'ccid':
        ctx.obj['dev'] = open_scard(reader)
    elif backend == 'sqlite':
        ctx.obj['dev'] = open_sqlite(os.path.join(CONFIG_HOME, 'tokens.db'))
    else:
        ctx.fail('Unknown backend "%s"' % (backend,))
    ctx.obj['controller'] = CliController(get_keystore(), backend, remember)
    ctx.obj['remember'] = remember


@cli.command()
@click.argument('query', nargs=-1, required=False)
@click.option('-t', '--timestamp', type=int, default=int(time()) + 5)
@click.pass_context
def show(ctx, query, timestamp):
    """
    Print one or more codes from a YubiKey.
    """
    dev = ctx.obj['dev']
    controller = ctx.obj['controller']

    creds = controller.read_creds(dev, timestamp)

    if creds is None:
        ctx.fail('No YubiKey found!')

    if query:
        query = ' '.join(query)
        # Filter based on query. If exact match, show only that result.
        matched = []
        for cred, code in creds:
            if cred.name == query:
                matched = [(cred, code)]
                break
            if query.lower() in cred.name.lower():
                matched.append((cred, code))

        # Only calculate Touch/HOTP codes if the credential is singled out.
        if len(matched) == 1:
            (cred, code) = matched[0]
            if not code:
                if cred.touch:
                    controller._prompt_touch()
                creds = [(cred, cred.calculate(timestamp))]
            else:
                creds = [(cred, code)]
        else:
            creds = matched

    print_creds(creds)


@cli.command()
@click.argument('key')
@click.option('-N', '--name', required=False, help='Credential name.')
@click.option(
    '-A', '--oath-type', type=click.Choice(['totp', 'hotp']), default='totp',
    help='Specify whether this is a time or counter-based OATH credential.')
@click.option('-D', '--digits', type=click.Choice(['6', '8']), default='6',
              callback=lambda c, p, v: int(v), help='Number of digits.')
@click.option(
    '-H', '--hmac-algorithm', type=click.Choice(['SHA1', 'SHA256']),
    default='SHA1', help='HMAC algorithm for OTP generation.')
@click.option(
    '-I', '--imf', type=int, default=0, help='Initial moving factor.')
@click.option('-T', '--touch', is_flag=True, help='Require touch.')
@click.option('-M', '--manual', is_flag=True, help='Require manual refresh.')
@click.pass_context
def put(ctx, key, name, oath_type, hmac_algorithm, digits, imf, touch, manual):
    """
    Stores a new OATH credential in the YubiKey.
    """
    controller = ctx.obj['controller']
    dev = ctx.obj['dev'] or ctx.fail('No YubiKey found!')

    if key.startswith('otpauth://'):
        parsed = parse_uri(key)
        key = parsed['secret']
        name = parsed.get('name')
        oath_type = parsed.get('type')
        hmac_algorithm = parsed.get('algorithm', 'SHA1').upper()
        digits = int(parsed.get('digits', '6'))
        imf = int(parsed.get('counter', '0'))

    if oath_type not in ['totp', 'hotp']:
        ctx.fail('Invalid OATH credential type')

    if hmac_algorithm == 'SHA1':
        algo = ALG_SHA1
    elif hmac_algorithm == 'SHA256':
        algo = ALG_SHA256
    elif hmac_algorithm == 'SHA512':
        algo = ALG_SHA512
    else:
        ctx.fail('Invalid HMAC algorithm')

    if algo not in controller.get_capabilities(dev).algorithms:
        ctx.fail('Selected HMAC algorithm not supported by device')

    if digits == 5 and name.startswith('Steam:'):
        # Steam is a special case where we allow the otpauth
        # URI to contain a 'digits' value of '5'.
        digits = 6

    if digits not in [6, 8]:
        ctx.fail('Invalid number of digits for OTP')

    digits = digits or 6
    unpadded = key.upper()
    key = b32decode(unpadded + '=' * (-len(unpadded) % 8))

    name = name or click.prompt('Enter a name for the credential')
    oath_type = TYPE_TOTP if oath_type == 'totp' else TYPE_HOTP
    try:
        controller.add_cred(dev, name, key, oath_type, digits=digits,
                            imf=imf, algo=algo, require_touch=touch,
                            require_manual_refresh=manual)
    except NoSpaceError:
        ctx.fail(
            'There is not enough space to add another credential on your'
            ' device. To create free space to add a new '
            'credential, delete those you no longer need.')


@cli.command()
@click.argument('name')
@click.pass_context
def delete(ctx, name):
    """
    Deletes a credential from the YubiKey.
    """
    controller = ctx.obj['controller']
    dev = ctx.obj['dev'] or ctx.fail('No YubiKey found!')
    controller.delete_cred(dev, name)
    click.echo('Credential deleted!')


@cli.group()
def password():
    """
    Manage the password used to protect access to the YubiKey.
    """


@password.command()
@click.password_option('-p', '--password')
@click.pass_context
def set(ctx, password):
    """
    Set a new password.
    """
    dev = ctx.obj['dev'] or ctx.fail('No YubiKey found!')
    controller = ctx.obj['controller']
    remember = ctx.obj['remember']
    controller.set_password(dev, password, remember)
    click.echo('New password set!')


@password.command()
@click.pass_context
def unset(ctx):
    """
    Removes the need to enter a password to access credentials.
    """
    dev = ctx.obj['dev'] or ctx.fail('No YubiKey found!')
    controller = ctx.obj['controller']
    controller.set_password(dev, '')
    click.echo('Password cleared!')


@password.command()
@click.pass_context
def forget(ctx):
    controller = ctx.obj['controller']
    controller.keystore.clear()


@cli.command()
@click.option('-f', '--force', is_flag=True,
              help='Confirm the action without prompting.')
@click.pass_context
def reset(ctx, force):
    """
    Deletes all stored OATH credentials from storage.
    """
    dev = ctx.obj['dev'] or ctx.fail('No YubiKey found!')
    controller = ctx.obj['controller']
    force or click.confirm('WARNING!!! Really delete all OATH '
                           'credentials from the YubiKey?', abort=True)

    controller.reset_device(dev)
    click.echo('The OATH functionality of your YubiKey has been reset.\n')


@cli.command(context_settings=dict(
    ignore_unknown_options=True,
    allow_extra_args=True
))
@click.option('-h', '--help', is_flag=True)
@click.pass_context
def gui(ctx, help):
    """
    Launches the Yubico Authenticator graphical interface.
    """
    try:
        import PyQt5
        assert PyQt5
    except ImportError:
        ctx.fail('GUI requires PyQt5 to run.')
    import yubioath.gui.__main__
    sys.argv.remove(ctx.command.name)
    sys.argv[0] = sys.argv[0] + ' ' + ctx.command.name
    yubioath.gui.__main__.main()


def intersects(a, b):
    return bool(set(a) & set(b))


def main():
    commands = list(cli.commands) + CLICK_CONTEXT_SETTINGS['help_option_names']

    buf = [sys.argv[0]]
    rest = sys.argv[1:]
    found_command = False
    while rest:
        first = rest.pop(0)
        if first in commands:
            found_command = True
            break  # We have a command, no more processing needed.
        for p in cli.params:
            if first in p.opts:  # first is an option.
                buf.append(first)
                if not p.is_flag and rest:  # Has a value.
                    buf.append(rest.pop(0))
                break  # Restart checking
        else:  # No match, put the argument back and stop.
            rest.insert(0, first)
            break

    if not found_command:  # No command found, default to "show".
        sys.argv = buf + ['show'] + rest

    try:
        cli(obj={})
    except KeyboardInterrupt:
        sys.stderr.write('\nInterrupted, exiting.\n')
        sys.exit(130)


if __name__ == '__main__':
    main()
