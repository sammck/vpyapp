#!/usr/bin/env python3
#
# MIT License
#
# Copyright (c) 2022 Sam McKelvie
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#

"""
Standalone python script (no dependencies other than standard python 3.7+) that
can create and manage a per-app virtualenv under ~/.local/cache and install a python app in it.
Suitable for running as a piped script from curl. See https://github.com/sammck/vpyapp.
"""

__version__ = "0.2.0"

from typing import (
    Optional,
    Sequence,
    MutableMapping,
    List,
    Dict,
    Any,
  )

import argparse
import sys
import os
import re
import pathlib
from unittest import result
from urllib.parse import urlparse, ParseResult, urlunparse, unquote as url_unquote
import subprocess
import tempfile
import hashlib

def searchpath_split(searchpath: Optional[str]=None) -> List[str]:
  if searchpath is None:
    searchpath = os.environ['PATH']
  result = [ x for x in searchpath.split(os.pathsep) if x != '' ]
  return result

def searchpath_join(dirnames: List[str]) -> str:
  return os.pathsep.join(dirnames)

def searchpath_normalize(searchpath: Optional[str]=None) -> str:
  return searchpath_join(searchpath_split(searchpath))

def searchpath_parts_contains_dir(parts: List[str], dirname: str) -> bool:
  dirname = os.path.abspath(os.path.normpath(os.path.expanduser(dirname)))
  return dirname in parts

def searchpath_contains_dir(searchpath: Optional[str], dirname: str) -> bool:
  return searchpath_parts_contains_dir(searchpath_split(searchpath), dirname)

def searchpath_parts_remove_dir(parts: List[str], dirname: str) -> List[str]:
  dirname = os.path.abspath(os.path.normpath(os.path.expanduser(dirname)))
  result = [ x for x in parts if x != dirname ]
  return result

def searchpath_remove_dir(searchpath: Optional[str], dirname: str) -> str:
  return searchpath_join(searchpath_parts_remove_dir(searchpath_split(searchpath), dirname))

def searchpath_parts_prepend(parts: List[str], dirname: str) -> List[str]:
  dirname = os.path.abspath(os.path.normpath(os.path.expanduser(dirname)))
  result = [dirname] + searchpath_parts_remove_dir(parts, dirname)
  return result

def searchpath_prepend(searchpath: Optional[str], dirname: str) -> str:
  return searchpath_join(searchpath_parts_prepend(searchpath_split(searchpath), dirname))

def searchpath_parts_prepend_if_missing(parts: List[str], dirname: str) -> List[str]:
  dirname = os.path.abspath(os.path.normpath(os.path.expanduser(dirname)))
  if dirname in parts:
    result = parts[:]
  else:
    result = [dirname] + parts
  return result

def searchpath_prepend_if_missing(searchpath: Optional[str], dirname: str) -> str:
  return searchpath_join(searchpath_parts_prepend_if_missing(searchpath_split(searchpath), dirname))

def searchpath_parts_force_append(parts: List[str], dirname: str) -> List[str]:
  dirname = os.path.abspath(os.path.normpath(os.path.expanduser(dirname)))
  result = searchpath_parts_remove_dir(parts, dirname) + [dirname]
  return result

def searchpath_force_append(searchpath: Optional[str], dirname: str) -> str:
  return searchpath_join(searchpath_parts_force_append(searchpath_split(searchpath), dirname))

def searchpath_parts_append(parts: List[str], dirname: str) -> List[str]:
  dirname = os.path.abspath(os.path.normpath(os.path.expanduser(dirname)))
  if dirname in parts:
    result = parts[:]
  else:
    result = parts + [dirname]
  return result

def searchpath_append(searchpath: Optional[str], dirname: str) -> str:
  return searchpath_join(searchpath_parts_append(searchpath_split(searchpath), dirname))

def deactivate_virtualenv(env: Optional[MutableMapping]=None):
  if env is None:
    env = os.environ
  if 'VIRTUAL_ENV' in env:
    venv = env['VIRTUAL_ENV']
    del env['VIRTUAL_ENV']
    if 'POETRY_ACTIVE' in env:
      del env['POETRY_ACTIVE']
    if 'PATH' in env:
      venv_bin = os.path.join(venv, 'bin')
      env['PATH'] = searchpath_remove_dir(env['PATH'], venv_bin)

def activate_virtualenv(venv_dir: str, env: Optional[MutableMapping]=None):
  venv_dir = os.path.abspath(os.path.normpath(os.path.expanduser(venv_dir)))
  venv_bin_dir = os.path.join(venv_dir, 'bin')
  if env is None:
    env = os.environ
  deactivate_virtualenv(env)
  env['VIRTUAL_ENV'] = venv_dir
  env['PATH'] = searchpath_prepend_if_missing(env['PATH'], venv_bin_dir)

class CmdExitError(RuntimeError):
  exit_code: int

  def __init__(self, exit_code: int=1, msg: Optional[str]=None):
    if msg is None:
      msg = f"Command exited with return code {exit_code}"
    super().__init__(msg)
    self.exit_code = exit_code

class ArgparseExitError(CmdExitError):
  pass

class NoExitArgumentParser(argparse.ArgumentParser):
  def exit(self, status=0, message=None):
    if message:
      self._print_message(message, sys.stderr)
    raise ArgparseExitError(status, message)

class Cli:
  home_dir = os.path.expanduser('~')
  pit_cache_dir = os.path.join(home_dir, '.cache', 'vpyapp')
  apps_dir = os.path.join(pit_cache_dir, 'apps')

  argv: Optional[Sequence[str]] = None
  verbose: bool = False
  args: argparse.Namespace
  _package_spec: Optional[str] = None
  _package_spec_hash: Optional[str] = None
  _no_venv_env: Optional[Dict[str, str]] = None
  _venv_env: Optional[Dict[str, str]] = None

  def __init__(self, argv: Optional[Sequence[str]]=None):
    self.argv = argv

  def cmd_bare(self) -> int:
    raise CmdExitError(msg="A subcommand is required")

  @property
  def package_spec(self) -> str:
    assert not self._package_spec is None
    return self._package_spec

  def normalize_package_spec(self, package_spec: str) -> str:
    if not ':' in package_spec and (
          '/' in package_spec or '#' in package_spec or package_spec.endswith('.gz')
        ):
      pathname = os.path.abspath(os.path.normpath(os.path.expanduser(package_spec)))
      package_spec = pathlib.Path(pathname).as_uri()

    return package_spec

  @package_spec.setter
  def package_spec(self, spec: str) -> str:
    spec = self.normalize_package_spec(spec)
    assert self._package_spec is None or self._package_spec == spec
    self._package_spec = spec
    return self._package_spec

  @property
  def package_spec_hash(self) -> str:
    if self._package_spec_hash is None:
      package_spec = self.package_spec
      h = hashlib.sha1(package_spec.encode('utf-8'))
      self._package_spec_hash = h.hexdigest()
    return self._package_spec_hash

  @property
  def app_dir(self) -> str:
    return os.path.join(self.apps_dir, self.package_spec_hash)

  @property
  def package_spec_filename(self) -> str:
    return os.path.join(self.app_dir, "package-spec.txt")

  @property
  def app_venv_dir(self) -> str:
    return os.path.join(self.app_dir, '.venv')

  @property
  def app_bin_dir(self) -> str:
    return os.path.join(self.app_venv_dir, 'bin')

  @property
  def no_venv_env(self) -> Dict[str, str]:
    if self._no_venv_env is None:
      no_venv_env = dict(os.environ)
      deactivate_virtualenv(no_venv_env)
      self._no_venv_env = no_venv_env
    return self._no_venv_env

  @property
  def venv_env(self) -> Dict[str, str]:
    if self._venv_env is None:
      app_venv_dir = self.app_venv_dir
      venv_env = dict(self.no_venv_env)
      activate_virtualenv(app_venv_dir, venv_env)
      self._venv_env = venv_env
    return self._venv_env

  @property
  def python_prog(self) -> str:
    return os.path.join(self.app_bin_dir, 'python3')

  @property
  def pip_prog(self) -> str:
    return os.path.join(self.app_bin_dir, 'pip3')

  @property
  def project_init_helper_prog(self) -> str:
    return os.path.join(self.app_bin_dir, 'project-init-helper')

  def remove_appdir(self) -> None:
    if os.path.exists(self.package_spec_filename):
      os.remove(self.package_spec_filename)
    if os.path.exists(self.app_dir):
      subprocess.call(['rm', '-fr', self.app_dir])

  def find_command_in_path(self, cmd: str) -> Optional[str]:
    try:
      result = subprocess.check_output(['which', cmd]).decode('utf-8').rstrip()
      if result == '':
        result = None
    except subprocess.CalledProcessError:
      result = None
    return result
  
  def module_exists(self, modname: str) -> bool:
    import importlib.util
    modspec = importlib.util.find_spec(modname)
    return not modspec is None

  def get_os_package_version(self, package_name: str) -> str:
    stdout_bytes = subprocess.check_output(
        ['dpkg-query', '--showformat=${Version}', '--show', package_name],
      )
    return stdout_bytes.decode('utf-8').rstrip()

  def os_package_is_installed(self, package_name: str) -> bool:
    result: bool = False
    try:
      if self.get_os_package_version(package_name) != '':
        result = True
    except subprocess.CalledProcessError:
      pass
    return result

  @property
  def local_bin_dir(self) -> str:
    return os.path.join(self.home_dir, '.local', 'bin')

  def get_local_pip(self) -> str:
    result = self.find_command_in_path('pip3')
    if result is None:
      local_bin_pip = os.path.join(self.local_bin_dir, 'pip3')
      if os.path.exists(local_bin_pip):
        result = local_bin_pip
      else:
        cache_dir = self.pit_cache_dir
        if not os.path.isdir(cache_dir):
          os.makedirs(cache_dir)
        get_pip_script = os.path.join(cache_dir, 'get-pip.py')
        import urllib.request
        urllib.request.urlretrieve("https://bootstrap.pypa.io/get-pip.py", get_pip_script)
        subprocess.check_call(['python3', get_pip_script, '--user'])
        if not os.path.exists(local_bin_pip):
          raise RuntimeError(f"{local_bin_pip} still does not exist after get-pip")
        subprocess.check_call([local_bin_pip, 'install', '--upgrade', '--user'])
        result = local_bin_pip
    return result

  def install_local_pip(self) -> str:
    result = self.find_command_in_path('pip3')
    if result is None:
      local_bin_pip = os.path.join(self.local_bin_dir, 'pip3')
      if os.path.exists(local_bin_pip):
        result = local_bin_pip
      else:
        cache_dir = self.pit_cache_dir
        if not os.path.isdir(cache_dir):
          os.makedirs(cache_dir)
        get_pip_script = os.path.join(cache_dir, 'get-pip.py')
        import urllib.request
        urllib.request.urlretrieve("https://bootstrap.pypa.io/get-pip.py", get_pip_script)
        subprocess.check_call(['python3', get_pip_script, '--user'])
        if not os.path.exists(local_bin_pip):
          raise RuntimeError(f"{local_bin_pip} still does not exist after get-pip")
        subprocess.check_call([local_bin_pip, 'install', '--upgrade', '--user', "pip"])
        result = local_bin_pip
    return result

  def install_venv(self) -> str:
    local_pip = self.install_local_pip()
    try:
      import venv
    except ImportError:
      subprocess.check_call([local_pip, 'install', '--upgrade', '--user', "venv"])
      try:
        import venv
      except ImportError:
        raise RuntimeError("venv module still does not exist after pip install")

  def do_install(
      self,
      package_spec: str,
      update: bool,
      clean: bool,
      stdout: Any = sys.stdout,
      stderr: Any = sys.stderr,
      ) -> str:
    self.package_spec = package_spec
    package_spec = self.package_spec
    app_dir = self.app_dir
    app_venv_dir = self.app_venv_dir


    try:
      os_packages: List[str] = []
      try:
        import distutils.cmd
      except ImportError:
        # ubuntu does not include distutils even though it is standard python
        os_packages.append('python3-distutils')

      if not self.os_package_is_installed('python3-dev'):
        # required for installation of many wheels
        os_packages.append('python3-dev')

      if len(os_packages) > 0:
        print(f"NOTE: sudo is required to install {os_packages}. Enter sudo password, or CTRL-C and manually install", file=sys.stderr)
        subprocess.check_call(['sudo', 'apt-get', 'install', '-y'] + os_packages)

      python = self.python_prog
      pip = self.pip_prog
      if (
            clean or
            not os.path.exists(self.package_spec_filename) or 
            not os.path.exists(python) or 
            not os.path.exists(pip)
          ):
        self.remove_appdir()
      if not os.path.isdir(app_dir):
        os.makedirs(app_dir)

      is_updated_venv = False
      if not os.path.exists(pip):
        self.install_venv()
      if not os.path.exists(app_venv_dir):
        import venv
        builder = venv.EnvBuilder(
            clear=clean,
          )
        builder.create(app_venv_dir)
        is_updated_venv = True
        
      no_venv_env = self.no_venv_env
      venv_env = self.venv_env

      if not os.path.exists(pip):
        cmd = [python, '-m', 'ensurepip']
        subprocess.check_call(cmd, env=venv_env, stdout=stdout, stderr=stderr)

      if update:
        cmd = [pip, 'install', '--upgrade', 'pip']
        subprocess.check_call(cmd, env=venv_env, stdout=stdout, stderr=stderr)

      if update or is_updated_venv:
        cmd = [pip, 'install']
        if update:
          cmd.append('--upgrade')
        cmd.append('wheel')
        subprocess.check_call(cmd, env=venv_env, stdout=stdout, stderr=stderr)

        cmd = [pip, 'install']
        if update:
          cmd.extend(['--upgrade', '--upgrade-strategy', 'eager'])
        cmd.append(self.package_spec)
        subprocess.check_call(cmd, env=venv_env, stdout=stdout, stderr=stderr)
      if not os.path.exists(self.package_spec_filename):
        with open(self.package_spec_filename, 'w', encoding='utf-8') as f:
          f.write(self.package_spec)
    except Exception:
      try:
        self.remove_appdir()
      except Exception:
        pass
      raise

    return app_dir

  def cmd_install(self) -> int:
    args = self.args
    update: bool = args.install_update
    clean: bool = args.install_clean
    package_spec: str = args.package_name
    app_path_file: Optional[str] = args.app_path_file

    app_dir = self.do_install(
        package_spec,
        update=update,
        clean=clean
      )

    if not app_path_file is None:
      with open(app_path_file, 'w', encoding='utf-8') as f:
        f.write(app_dir)

    return 0

  def cmd_run(self) -> int:
    args = self.args
    update: bool = args.install_update
    clean: bool = args.install_clean
    package_spec: str = args.package_name
    app_cmd: List[str] = args.app_cmd
    if self.verbose:
      self.do_install(
          package_spec,
          update=update,
          clean=clean,
        )
    else:
      with tempfile.NamedTemporaryFile() as f_install_log:
        try:
          self.do_install(
              package_spec,
              update=update,
              clean=clean,
              stdout=f_install_log,
              stderr=subprocess.STDOUT
            )
        except Exception as e:
          f_install_log.flush()
          f_install_log.seek(0)
          sys.stderr.write(f_install_log.read().decode('utf-8'))
          raise

    if len(app_cmd) > 0:
      cmd = app_cmd[:]
      cmd[0] = os.path.abspath(os.path.join(
          self.app_bin_dir, os.path.normpath(os.path.expanduser(cmd[0]))
        ))

      venv_env = self.venv_env
      subprocess.check_call(
          cmd,
          env=venv_env
        )

    return 0

  def cmd_version(self) -> int:
    print(__version__)
    return 0

  def cmd_ls(self) -> int:
    apps_dir = self.apps_dir
    if os.path.exists(apps_dir):
      results: List[str] = []
      for entry in os.listdir(apps_dir):
        package_spec_filename = os.path.join(apps_dir, entry, "package-spec.txt")
        if os.path.exists(package_spec_filename):
          with open(package_spec_filename, encoding='utf-8') as f:
            package_spec = f.read().rstrip()
            results.append(package_spec)
      results.sort()
      if len(results) > 0:
        print('\n'.join(results))
    return 0

  def cmd_locate(self) -> int:
    self.package_spec = self.args.package_name
    app_dir = self.app_dir
    if not os.path.exists(app_dir):
      raise CmdExitError(msg=f"Package is not installed (must match exactly): {self.package_spec}")
    print(self.app_dir)
    return 0

  def cmd_uninstall(self) -> int:
    self.package_spec = self.args.package_name
    app_dir = self.app_dir
    if not os.path.exists(app_dir):
      raise CmdExitError(msg=f"Package is not installed (must match exactly): {self.package_spec}")
    subprocess.call(['rm', '-fr', app_dir])
    return 0

  def get_parser(self) -> argparse.ArgumentParser:
    parser = NoExitArgumentParser()
    parser.set_defaults(func=self.cmd_bare)
    parser.add_argument(
        '--traceback', "--tb",
        action='store_true',
        default=False,
        help='Display detailed exception information')
    parser.add_argument("-v", "--verbose",
        help="Verbose output",
        default=False,
        action="store_true"
      )

    subparsers = parser.add_subparsers(
                        title='Commands',
                        description='Valid commands',
                        help='Additional help available with "vpyapp.py <command-name> -h"')

   # ======================= version

    parser_version = subparsers.add_parser(
        'version',
        description='''Display the version of vpyapp.py being used.'''
      )
    parser_version.set_defaults(func=self.cmd_version)

    # ======================= ls

    parser_ls = subparsers.add_parser(
        'ls',
        description='''List installed vpyapp packages.'''
      )
    parser_ls.set_defaults(func=self.cmd_ls)

    # ======================= install

    parser_install = subparsers.add_parser(
        'install',
        description='''Install a python app/package in its own virtualenv private to this user.'''
      )
    parser_install.add_argument(
        '-u', '--update',
        dest="install_update",
        default=False,
        action='store_true',
        help='Update the package if it is already installed')
    parser_install.add_argument(
        '--clean',
        dest="install_clean",
        default=False,
        action='store_true',
        help='Force a clean installation of the package')
    parser_install.add_argument(
        '-o', '--app-path-file',
        default=None,
        help='The name of a file  to which the installed application\'s path will be written')
    parser_install.add_argument('package_name',
                        help='The package to install, as provided to "pip3 install".')
    parser_install.set_defaults(func=self.cmd_install)

    # ======================= uninstall

    parser_uninstall = subparsers.add_parser(
        'uninstall',
        description='''Uninstall a previously installed package.'''
      )
    parser_uninstall.add_argument('package_name',
                        help='The previously installed package, exactly as provided to "install" or "run".')
    parser_uninstall.set_defaults(func=self.cmd_uninstall)

    # ======================= locate

    parser_locate = subparsers.add_parser(
        'locate',
        description='''Get the app directory of a previously installed package.'''
      )
    parser_locate.add_argument('package_name',
                        help='The previously installed package, exactly as provided to "install" or "run".')
    parser_locate.set_defaults(func=self.cmd_locate)

    # ======================= run

    parser_run = subparsers.add_parser(
        'run',
        description='''Install a python app/package in its own virtualenv and run a command in the virtualenv.'''
      )
    parser_run.add_argument(
        '-u', '--update',
        dest="install_update",
        default=False,
        action='store_true',
        help='Update the package if it is already installed')
    parser_run.add_argument(
        '--clean',
        dest="install_clean",
        default=False,
        action='store_true',
        help='Force a clean installation of the package')
    parser_run.add_argument('package_name',
                        help='The package to install, as provided to "pip3 install".')
    parser_run.add_argument('app_cmd', nargs=argparse.REMAINDER,
                        help='Command and arguments as would be used within the virtualenv.')
    parser_run.set_defaults(func=self.cmd_run)

    return parser

  def __call__(self) -> int:
    parser = self.get_parser()
    try:
      args = parser.parse_args(self.argv)
    except ArgparseExitError as ex:
      return ex.exit_code
    traceback: bool = args.traceback
    try:
      self.verbose = args.verbose
      self.args = args
      rc = args.func()
    except Exception as ex:
      if isinstance(ex, CmdExitError):
        rc = ex.exit_code
      else:
        rc = 1
      if rc != 0:
        if traceback:
          raise

        print(f"vpyapp: error: {ex}", file=sys.stderr)
    return rc

def run(argv: Optional[Sequence[str]]=None) -> int:
  try:
    rc = Cli(argv)()
  except CmdExitError as ex:
    rc = ex.exit_code
  return rc

if __name__ == "__main__":
  sys.exit(run())
