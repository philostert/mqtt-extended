###############
Getting Started
###############

.. role:: bash(code)
   :language: bash

Installation
============

Running :bash:`pip install -r requirements.txt` should get you started.

Running the Broker
==================

Hell, just run :bash:`./start_broker`!

Command Line Options
--------------------

You know the :bash:`--help` paradigm, do you?

--authfile                       Authentication and authorization config file
                                 path
--help                           show this help information
--password                       Password for client authentication
--redis                          Use redis as queue backend (default False)
--rhost                          Redis host address (default localhost)
--rpassword                      Redis password
--rport                          Redis host port (default 6379)
--ssl                            Use SSL/TLS on socket (default False)
--sslcert                        SSL/TLS Certificate file path
--sslkey                         SSL/TLS Key file path
--webauth                        Authentication and authorization web API
                                 address

/usr/lib/python3.5/site-packages/tornado/log.py options:

--log_file_max_size              max size of log files before rollover
                                 (default 100000000)
--log_file_num_backups           number of log files to keep (default 10)
--log_file_prefix=PATH           Path prefix for log files. Note that if you
                                 are running multiple tornado processes,
                                 log_file_prefix must be different for each
                                 of them (e.g. include the port number)
--log_to_stderr                  Send log output to stderr (colorized if
                                 possible). By default use stderr if
                                 --log_file_prefix is not set and no other
                                 logging is configured.
--logging=debug|info|warning|error|none  
                                   Set the Python log level. If 'none', tornado
                                   won't touch the logging configuration.
                                   (default info)

Message Exchanging
==================

We do read StackOverflow, sometimes.

Configuration Scripts
=====================

There is no such thing.
