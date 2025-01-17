Contributing to Protean
=======================

Thank you for considering contributing to Protean!

Support questions
-----------------

Please don't use the issue tracker for this. The issue tracker is a tool
to address bugs and feature requests in Protean itself. Use one of the
following resources for questions about using Protean or issues with your
own code:

-   The ``#questions`` channel on our Discord chat:
    https://discord.gg/fwhg7JKxNy
-   Ask on `Stack Overflow`_. Search with Google first using:
    ``site:stackoverflow.com protean {search term, exception message, etc.}``
-   Ask on our `GitHub Discussions`_.

.. _Stack Overflow: https://stackoverflow.com/questions/tagged/protean?tab=Frequent
.. _GitHub Discussions: https://github.com/proteanhq/protean/discussions

Reporting issues
----------------

Include the following information in your issue:

-   Describe what you expected to happen.
-   If possible, include a `minimal reproducible example`_ to help us
    identify the issue. This also helps check that the issue is not with
    your own code.
-   Describe what actually happened. Include the full traceback if there
    was an exception.
-   List your Python and Protean versions. If possible, check if this
    issue is already fixed in the latest releases or the latest code in
    the repository.

.. _minimal reproducible example: https://stackoverflow.com/help/minimal-reproducible-example

Submitting patches
------------------

If there is not an open issue for what you want to submit, prefer
opening one for discussion before working on a PR. You can work on any
issue that doesn't have an open PR linked to it or a maintainer assigned
to it. These show up in the sidebar. No need to ask if you can work on
an issue that interests you.

Include the following in your patch:

-   Use `Black`_ to format your code. This and other tools will run
    automatically if you install `pre-commit`_ using the instructions
    below.
-   Include tests if your patch adds or changes code. Make sure the test
    fails without your patch.
-   Update any relevant docs pages and docstrings. Docs pages and
    docstrings should be wrapped at 72 characters.
-   Add an entry in ``CHANGES.rst``. Use the same style as other
    entries. Also include ``.. versionchanged::`` inline changelogs in
    relevant docstrings.

.. _Black: https://black.readthedocs.io
.. _pre-commit: https://pre-commit.com

First time setup
````````````````

-   Download and install the `latest version of git`_.
-   Configure git with your `username`_ and `email`_.

    .. code-block:: text

        $ git config --global user.name 'your name'
        $ git config --global user.email 'your email'

-   Make sure you have a `GitHub account`_.
-   Fork Flask to your GitHub account by clicking the `Fork`_ button.
-   `Clone`_ the main repository locally.

    .. code-block:: text

        $ git clone https://github.com/proteanhq/protean
        $ cd protean
-   Add your fork as a remote to push your work to. Replace
    ``{username}`` with your username. This names the remote "fork", the
    default Protean remote is "origin".

    .. code-block:: text

        $ git remote add fork https://github.com/{username}/flask

-   Create a virtualenv.

    .. tabs::

       .. group-tab:: Linux/macOS

          .. code-block:: text

             $ python3 -m venv env
             $ . env/bin/activate

       .. group-tab:: Windows

          .. code-block:: text

             > py -3 -m venv env
             > env\Scripts\activate

-   Upgrade pip and setuptools.

    .. code-block:: text

        $ python -m pip install --upgrade pip setuptools

-   Install the development dependencies, then install Protean in editable
    mode.

    .. code-block:: text

        $ pip install -e .[all] && pip install -e .

-   Install the pre-commit hooks.

    .. code-block:: text

        $ pre-commit install

.. _latest version of git: https://git-scm.com/downloads
.. _username: https://docs.github.com/en/github/using-git/setting-your-username-in-git
.. _email: https://docs.github.com/en/github/setting-up-and-managing-your-github-user-account/setting-your-commit-email-address
.. _GitHub account: https://github.com/join
.. _Fork: https://github.com/proteanhq/protean/fork
.. _Clone: https://docs.github.com/en/github/getting-started-with-github/fork-a-repo#step-2-create-a-local-clone-of-your-fork

Start coding
````````````

-   Create a branch to identify the issue you would like to work on. If
    you're submitting a bug or documentation fix, branch off of the
    latest ".x" branch.

    .. code-block:: text

        $ git fetch origin
        $ git checkout -b your-branch-name origin/0.6.x

    If you're submitting a feature addition or change, branch off of the
    "master" branch.

    .. code-block:: text

        $ git fetch origin
        $ git checkout -b your-branch-name origin/master

-   Using your favorite editor, make your changes,
    `committing as you go`_.
-   Include tests that cover any code changes you make. Make sure the
    test fails without your patch. Run the tests as described below.
-   Push your commits to your fork on GitHub and
    `create a pull request`_. Link to the issue being addressed with
    ``fixes #123`` or ``closes #123`` in the pull request.

    .. code-block:: text

        $ git push --set-upstream fork your-branch-name

.. _committing as you go: https://dont-be-afraid-to-commit.readthedocs.io/en/latest/git/commandlinegit.html#commit-your-changes
.. _create a pull request: https://docs.github.com/en/github/collaborating-with-issues-and-pull-requests/creating-a-pull-request

Running the tests
`````````````````

Run the basic test suite:

.. code-block:: text

    $ make test

This runs the tests with default adapters, which is usually
sufficient. CI will run the full suite when you submit your pull
request.

If you want to test Protean against all adapters, you can
run the full test suite after bringing up the Docker containers
running database and message broker services.

.. code-block:: text

    $ make test-full

Running test coverage
`````````````````````

Generating a report of lines that do not have test coverage can indicate
where to start contributing. Run ``pytest`` using ``coverage`` and
generate a report.

.. code-block:: text

    $ make cov

Open ``htmlcov/index.html`` in your browser to explore the report.

Read more about `coverage <https://coverage.readthedocs.io>`__.

Building the docs
`````````````````

Build the docs in the ``docs`` directory using Sphinx.

.. code-block:: text

    $ make html

Open ``build/html/index.html`` in your browser to view the docs.

Read more about `Sphinx <https://www.sphinx-doc.org/en/stable/>`__.
