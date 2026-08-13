# ControlThings User Interface

The `ctui` is a library for creating terminal-based user interfaces, and is used in all the ControlThings tools at controlthings.io.  It is similar to using Click or Python's standard Cmd library, but with a curses-like interface written in pure Python.

# Installation

Ctui is primarily developed on Linux, but should work in both Mac and Windows as well.

As long as you have git and Python 3.8 or later installed, all you should need to do is:

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

Of course you can configure you app in a number of different ways by modifying your app's attributes or by adding your own custom commands.   Check out the `examples` folder to walk you through some of these.  For more complex examples how to use `ctui`, check out the various ControlThings Tools, most of which use `ctui`.  You can find these at <https://github.com/ControlThingsTools>.

# Fork and Develop

To set up a development environment for `ctui`, you will first need to install [uv](<https://docs.astral.sh/uv/>) which is used to manage all the project dependencies and publish the pypi packages.  I strongly recommend checking out the website and at least reading through the [Basic Project Concepts](https://docs.astral.sh/uv/concepts/projects/) page, but if you want the TLDR, just run the following command to install `uv`:

    curl -LsSf https://astral.sh/uv/install.sh | sh

Once `uv` is installed, pull the `ctui` repo and :

    git clone https://github.com/ControlThings-io/ctui.git
    cd ctui
    uv sync

To try out the project examples files, run:

    uv run examples/default.py
    uv run examples/filesystem.py

That last command will open a shell in a python virtual environment where you can do live edits to the code.  If you are a VS Code user, VS Code will automatically load the repo configs with all the linting rules I use through the repo, and should automatically open the debug tools and terminal inside the virtual environment.

# Author

* Justin Searle <justin@controlthings.io>
