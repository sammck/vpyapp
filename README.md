vpyapp.py: Standalone virtualized Python app installer
===================================================

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Latest release](https://img.shields.io/github/v/release/sammck/vpyapp.svg?style=flat-square&color=b44e88)](https://github.com/sammck/vpyapp/releases)

`vpyapp.py` is a simple, single-file script that can be sourced with curl to bootstrap installation
and launching of of cached virtualized python applications.

Table of contents
-----------------

* [Introduction](#introduction)
* [Installation](#installation)
* [Usage](#usage)
  * [Command line](#command-line)
  * [API](api)
* [Known issues and limitations](#known-issues-and-limitations)
* [Getting help](#getting-help)
* [Contributing](#contributing)
* [License](#license)
* [Authors and history](#authors-and-history)


Introduction
------------

Python script `vpyapp.py` is intended to be sourced with curl and run directly. it manages a set of named
"virtual python applications", each with their own dedicated directory and virtualenv under
`~/.cache/vpyapp/apps`. It's simple CLI allows the user to run commands provided by isolated cached
python applications, without requiring explicit creating of virtualenvs, installation of prerequisites,
etc.

Installation
------------

### Prerequisites

**Python**: Python 3.7+ is required. See your OS documentation for instructions.


### From PyPi

The current released version of `secret-kv` can be installed with 

```bash
pip3 install secret-kv
```

### From GitHub

[Poetry](https://python-poetry.org/docs/master/#installing-with-the-official-installer) is required; it can be installed with:

```bash
curl -sSL https://install.python-poetry.org | python3 -
```

Clone the repository and install secret-kv into a private virtualenv with:

```bash
cd <parent-folder>
git clone https://github.com/sammck/secret-kv.git
cd secret-kv
poetry install
```

You can then launch a bash shell with the virtualenv activated using:

```bash
poetry shell
```


Usage
=====

Command Line
------------

### Web-sourced
The intended use of `vpyapp.py` is as a zero-install curl-sourced script; e.g.,:

```bash
curl -sSL https://raw.githubusercontent.com/sammck/vpyapp/latest/vpyapp.py | python3 - <vpyapp-command> [<arg>...]
```
The `latest` tag will be maintained on this repository to point to the latest stable version.

### Locally

Alternatively, `vpyapp.py` may be copied anyhere and run directly as a script; e.g.,:

```bash
./vpyapp.py  <vpyapp-command> [<arg>...]
```

### Usage
Regardless of whether the script is sourced locally or via curl, the command-line interface is the same:

```bash
usage: vpyapp.py [-h] [--traceback] [-v] {version,install,run} ...

optional arguments:
  -h, --help            show this help message and exit
  --traceback, --tb     Display detailed exception information
  -v, --verbose         Verbose output

```

#### Display the `vpyapp.py` version:
```bash
usage: vpyapp.py version [-h]

Display the version of vpyapp.py being used.
```

#### Install or update a vpyapp without invoking a command in the vpyapp
```bash
usage: vpyapp.py install [-h] [-n APP_NAME] [-u] [--clean] [-o APP_PATH_FILE] package_name

Install a python app/package in its own virtualenv private to this user.

positional arguments:
  package_name          The package to install, as provided to "pip3 install".

optional arguments:
  -h, --help            show this help message and exit
                        Local name of the app. By default, derived from package_name
  -u, --update          Update the package if it is already installed
  --clean               Force a clean installation of the package
  -o APP_PATH_FILE, --app-path-file APP_PATH_FILE
                        The name of a file to which the installed application path will be written
```

#### Silently install/update a vpyapp if necessary, then invoke a command in the virtualenv of the vpyapp
```bash
usage: vpyapp.py run [-h] [-n APP_NAME] [-u] [--clean] package_name ...

Install a python app/package in its own virtualenv and run a command in the virtualenv.

positional arguments:
  package_name          The package to install, as provided to "pip3 install".
  app_cmd...            Command and arguments as would be used within the virtualenv.

optional arguments:
  -h, --help            show this help message and exit
  -u, --update          Update the package if it is already installed
  --clean               Force a clean installation of the package
```

API
---

`vpayapp.py` may be imported as a module and its `run` function can be called from other scripts if desired.

Known issues and limitations
----------------------------

* Import/export are not yet supported.

Getting help
------------

Please report any problems/issues [here](https://github.com/sammck/secret-kv/issues).

Contributing
------------

Pull requests welcome.

License
-------

`vpyapp.py` is distributed under the terms of the [MIT License](https://opensource.org/licenses/MIT).  The license applies to this file and other files in the [GitHub repository](http://github.com/sammck/vpyapp) hosting this file.

Authors and history
-------------------

The author of `vpyapp.py` is [Sam McKelvie](https://github.com/sammck).
