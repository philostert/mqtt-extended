###############
Project Roadmap
###############

Milestone IoT #1
================

- Message Broker acts as an intermediary
- Relaying messages between devices and Relayr cloud

Milestone IoT #2
================

- Fully functional local Message Broker with internal database

Milestone IoT #3
================

- Capability to handle remote publications and subscriptions

----

########################
Original Project Roadmap
########################
.. important::
   These features are presented in *no special order*, neither is there a
   development schedule for them. If your project requires any of these features
   we encourage you to visit the corresponding BitBucket issue and express
   the situation.

   You are also welcome to implement these and open a pull request.

MQTT Compliance
===============
    #. MQTT Strict Mode `[issue #1] <https://bitbucket.org/tegris/mqtt-broker/issue/1/mqtt-strict-mode>`_
    #. QoS Level 2, exactly once delivery `[issue #2] <https://bitbucket.org/tegris/mqtt-broker/issue/2/qos-2-support>`_
    #. Last Will message `[issue #3] <https://bitbucket.org/tegris/mqtt-broker/issue/3/support-last-will>`_

MQTT Protocol Extensions
========================
    #. Authentication support `[issue #4] <https://bitbucket.org/tegris/mqtt-broker/issue/4/authentication-support>`_
    #. Authorization support `[issue #5] <https://bitbucket.org/tegris/mqtt-broker/issue/5/authorization-support>`_
    #. Handling compressed publish messages (gzip) `[issue #6] <https://bitbucket.org/tegris/mqtt-broker/issue/6/message-compression>`_
    #. Automatic compressing messages based on payload size `[issue #7] <https://bitbucket.org/tegris/mqtt-broker/issue/7/automatic-compression-based-on-payload>`_

Integration Testing
===================
    #. Expand the test suite for QoS 0 `[issue #8] <https://bitbucket.org/tegris/mqtt-broker/issue/8/expand-test-suite-for-qos-0>`_
    #. Expand the test suite for QoS 2 `[issue #9] <https://bitbucket.org/tegris/mqtt-broker/issue/9/expand-test-suite-for-qos-2>`_

Dependency Review
=================
    #. Consider Python AsyncIO instead of TornadoWeb `[issue #10] <https://bitbucket.org/tegris/mqtt-broker/issue/10/consider-replacing-tornadoweb-in-favor-of>`_

Message Store Support
=====================
    #. File based message store `[issue #11] <https://bitbucket.org/tegris/mqtt-broker/issue/11/file-based-message-store>`_
    #. Redis backend `[issue #12] <https://bitbucket.org/tegris/mqtt-broker/issue/12/redis-based-message-store>`_
