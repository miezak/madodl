madodl
======

`madodl` is an operating system independent Python CLI script that downloads
manga from [madokami](https://manga.madokami.com).

Installing
----------

Dependencies:
* >= **python 3.4**
* **pycURL**
* **PyYAML**

#### pip

```sh
# globally
$ sudo pip3 install 'git+https://github.com/miezak/madodl'

# locally
$ pip3 install --user 'git+https://github.com/miezak/madodl'

# download the latest development version
$ pip3 install --user 'https://github.com/miezak/madodl/archive/devel.zip'
```

#### Source

```sh
$ git clone https://github.com/miezak/madodl
$ cd madodl
$ python3 setup.py build
$ python3 setup.py install
```

The development branch is __devel__.
```sh
$ git checkout devel
```

How to use it
-------------

`madodl` is designed to be simple to use.

Download all of Berserk:

```sh
$ madodl -m berserk
```

Download volume 10 of Berserk:

```sh
$ madodl -m berserk v10
```

The -m switch can be used as many times as needed:

```sh
$ madodl -m one v1 -m two v1 c3 -m three # etc.
```

Multiple volumes/chapters can be specified with ranges and commas.
Some examples:

```
# volumes 1 to 5
v1-5

# all volumes from 5 to latest volume
v5-

# volumes 1-5, 7 and 12
v1-5,7,12

# half-volumes
v1-5.5,10.5-12
```

Chapters use this same exact format. Volumes and chapters are separated as
separate arguments on the command-line. If there are volumes and chapters that
aren't separated with a space, `madodl` doesn't make any assumptions and just
splits the two as normal.

```sh
$ madodl -m berserk v3,4 c150-165
```
is the same as
```sh
$ madodl -m berserk v3,4,c150-165
```

`madodl` tries to be flexible about ranges. For example, if a range is
non-increasing, the start and end will be switched around:

```
v10-5
# will be seen as
v5-10
```
Also, the numbers need not be in increasing order:
```
# perfectly valid
ch1,20,3,10,5
```

The default folder to store downloaded manga is specified in the config file.
If this option is empty, `madodl` defaults to the current working directory. You
can override the default with the -o switch on the command-line:

```sh
$ madodl -m berserk v1 -o /home/user/manga
```

Configuring
-----------

`madodl` looks for the config file in a few common locations.

On Unix systems, in order:

```
~/.config/madodl/config.yml
~/.madodl/config.yml
~/.madodl.yml
```

On Windows:

```
\Users\{youruser}\.madodl\config.yml
```

The default configuration file is distributed with the source [here](/madodl/config.yml).
