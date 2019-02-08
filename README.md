# Control Things Serial

ctui is a library for creating terminal-based user interfaces, and is used in all the ControlThings tools at controlthings.io.  It is similar to using Click or Python's standard Cmd library, but with a curses-like interface written in pure Python.

# Installation:

As long as you have git and Python 3.5 or later installed, all you should need to do is:

```
git clone https://github.com/ControlThingsTools/ctui.git
cd ctui
pip3 install -r requirements.txt
```

# Usage:

Import the library, instantiate a Ctui object, and start the ctui application, like:

```
from ctui import Ctui

myapp = Ctui()
myapp.run()
```

Of course you can configure you app in a number of different ways by modifying your app's attributes or by adding your own custom commands.   Check out the examples folder to walk you through some of these.

# Platform Independence

Python 3.5+ and all dependencies are available for all major operating systems.  It is primarily developed on MacOS and Linux, but should work in Windows as well.

# Author

* Justin Searle <justin@controlthings.io>
