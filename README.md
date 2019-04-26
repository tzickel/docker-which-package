# What is it ?

A utility to help you figure out which package you need to install in order to get your Dockerfile to build.

The current set of limitations should at least make this a useful exploratory tool for APT based distributions.

# Known issues

* Shell is currently hard coded to "/bin/sh -c" (the default docker SHELL directive)
* The RUN directive has not been stress tested against weird syntax
* For now the failing RUN directive needs to be able to run apt-get commands (by default running as USER root)
* For now it works with Dockerfile which do not need a context (self containing)
* The image will be running with the following options to allow strace to run: "--cap-add=SYS_PTRACE --pid=host"

# Requirements

* Python 2.7 or 3
* Docker runtime that can build and run the image
* Linux APT based Dockerfile (such as debian, ubuntu)

# Quickstart

Let's take the following simple Dockerfile, and try to make it work:

```Dockerfile
FROM debian:stretch-slim

RUN python -c "import numpy; print(numpy.version.version)"
```

Trying to docker build will fail because the basic image does not have nor python nor numpy. So let's run:

```bash
python resolve.py
```

And it tells out we need to install python-minimal, So let's modify the Dockerfile:

```Dockerfile
FROM debian:stretch-slim

RUN apt-get update && apt-get install -y python-minimal

RUN python -c "import numpy; print(numpy.version.version)"
```

Now building fails, because it does not know what numpy is yet:

```bash
python resolve.py
```

Tells us to now install python-numpy package (since python access the path by directory and not by file, it also gives us a false positive we can ignore, python-numpy-dbg):

```bash
python resolve.py
```

And thus here is the final working Dockerfile:

```Dockerfile
FROM debian:stretch-slim

RUN apt-get update && apt-get install -y python-minimal python-numpy

RUN python -c "import numpy; print(numpy.version.version)"
```
