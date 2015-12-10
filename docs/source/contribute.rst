##########
Contribute
##########

Software Development
====================
Clone the `project's repository`_ from BitBucket, do some good and open a pull
request.

.. attention::
   Check the open issues and pull requests to avoid reinventing the wheel.

   If you want to collaborate in solving an issue or developing a feature,
   please contact the person doing it through the issue tracker.

Bug Tracking
============
So you found a nasty bug?

Take a look at the `issue tracker`_ and see if it was already reported. If you
find a corresponding entry please upvote it and consider tackling the issue or
helping those already involved. If you manage to solve the bug, open a pull
request so we fix project for everyone.

If you found a **previously unknown exemplar of software development fauna**,
please create a new entry and describe the bug as best as you can, possibly
writing a unittest for it. Finally, state if you plan to solve it yourself
or need help.

Documentation
=============
You will find this documentation bundled with the source code, under the *docs*
directory, in the `project's repository`_. It should be easy to compile it using
the command::

    you@your-pc:somewhere/mqtt-broker/docs$ make html

The results are built and stored at the *build* directory. The following steps
are recommended:

    #. Edit a page under *sources* directory;
    #. Rebuild the html results (using the aforementioned command);
    #. Check the results by opening *build/index.html*;
    #. Repeat to your satisfaction;
    #. Open a pull request so everyone can benefit from your work.

.. _`project's repository`: https://bitbucket.org/tegris/mqtt-broker/
.. _issue tracker: https://bitbucket.org/tegris/mqtt-broker/issues