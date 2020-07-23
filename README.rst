Nuitka Speedcenter
------------------

Welcome to Nuitka speedcenter, the underlying tool behind the site dedicated
to performance and Nuitka: https://speedcenter.nuitka.net

Currently this is very newly released and relatively ugly, hope is for you
people to join and improve this in entirely new ways.

Installation
------------

This needs Python 3.7 and Linux currently. Also valgrind will have to be
installed.

Then do these commands (may take a while, it is compile parts of the
dependencies via C it seems, and not all of it is available as wheels):

.. code-block::

   python3.7 -m pip install pipenv
   python3.7 -m pipenv install

Now the tools are runnable, the main frontend currently for building the
Nikola site is this:

.. code-block::

   python3.7 -m pipenv run ./update.py --update-all

Note it will attempt to deploy and fail. The UI is currently not really good.

To look at it, consider using this:

.. code-block::

   python3.7 -m pipenv run nikola serve

Improvements Needed
-------------------

Construct based tests are a nice way to take performance. But maybe test cases
should be generated via Jinja2 and not via hand made pre-processor. Not sure
really, because one of my initial goals in doing it was to have proper syntax
for Python. But Jinja2 will be better at generating and therefore also at
maintaining more test cases easier.

For the rendering, Nikola and a graphing plugin are used. Nikola has a better
thing for diff display. We either expand on this, or we turn to something
entirely different.

And lastly, on Windows there is no Valgrind. Is there an alternative way to
measure performance as accurate as Valgrind can for Linux?
