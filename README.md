# ControlThings User Interface

The `ctui` is a library for creating terminal-based user interfaces, and is used in all the ControlThings tools at controlthings.io.  It is similar to using Click or Python's standard Cmd library, but with a curses-like interface written in pure Python.

# Installation

Ctui is primarily developed on Linux, but should work in both Mac and Windows as well.

As long as you have git and Python 3.6 or later installed, all you should need to do is:

```
pip3 install ctui
```

# Usage

Import the library, instantiate a Ctui object, and start the ctui application, like:

```
from ctui import Ctui

myapp = Ctui()
myapp.run()
```

Of course you can configure you app in a number of different ways by modifying your app's attributes or by adding your own custom commands.   Check out the `examples` folder to walk you through some of these.  For more complex examples how to use ctui, check out the various ControlThings Tools, most of which use ctui.  You can find these at <https://github.com/ControlThingsTools>.

# Fork and Develop

To set up a development environment for ctui, you will first need to install [Python Poetry](<https://python-poetry.org>) which is used to manage all the project dependencies and publish the pypi packages.  I strongly recommend checking out the website and at least reading through the [Basic Usage](https://python-poetry.org/docs/basic-usage/) page, but if you want the TLDR, just run:

    curl -sSL https://install.python-poetry.org | python3 -

Once Poetry is installed, pull the repo and :

    git clone https://github.com/ControlThings-io/ctui.git
    cd ctui
    poetry install
    poetry shell

That last command will open a shell in a python virtual environment where you can do live edits to the code.  If you are a VS Code user, VS Code will automatically load the repo configs with all the linting rules I use through the repo, and should automatically open the debug tools and terminal inside the virtual environment.

# Author

* Justin Searle <justin@controlthings.io>
