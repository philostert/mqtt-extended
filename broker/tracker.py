from broker.exceptions import BeginTracking, EndTracking
import re

# Two basic alternatives "one-topic-level" and "at-least-two-topic-levels" in order to not match empty strings.
# Per level literal character group %(l)s excludes certain unicode points.
# Unicode exclusions defined @ MQTT Version 3.1.1, Section 1.5.3 UTF-8 encoded strings.
re_match_valid_mask = re.compile(r'^([+#]|%(l)s+)$|^(([+]|%(l)s*)/(([+]|%(l)s*)/)*([+#]|%(l)s*))$' %
                                 {'l': r'[^+#/\u0000\ud800-\udfff\u0001-\u001f\u007f-\u009f]'}) # group of literals


class Tracker:
    def __init__(self):
        pass


class TopicTracker(Tracker):
    def __init__(self):
        super().__init__()

def foo(mask, qos, client):
    pass
    topic_levels = mask.split("/")


# FIXME don't ask, tell! Let the tracker also do forwarding decisions and their execution?!
class SubMaskTracker(Tracker):
    def add_sub(mask, qos, client):
        assert isinstance(mask, str)
        assert isinstance(qos, int)
        if not re_match_valid_mask.match(mask):
            raise ValueError

        topic_levels = mask.split("/")
        for level in topic_levels:
            self.

    class _LevelEntry:
        def __init__(self, level_name):
            self._sublevels = dict()        # topic level key e.g. '+', '#', 'temperature'  => _LevelEntry
            self._subscriptions = dict()    # client.uid  => qos
            self._match_all = False
            if level_name == '#':
                self._match_all = True

        def get_subscriptions(self, subsequent_levels):
            if not subsequent_levels or self._match_all:
                return self._subscriptions.copy()
            else:
                assert (subsequent_levels, list)
                # cut list and determine next sub levels to walk
                subsequent_levels = subsequent_levels.copy()
                next_literal = subsequent_levels.pop(0)
                next_levels = {key for key in {'+', '#', next_literal} if key in self._sublevels}

                # create new mapping where all subscriptions are merged
                matches = type(self._subscriptions)()
                for key in next_levels:
                    additional_matches = self._sublevels[key].get_subscriptions(subsequent_levels)
                    # get maximum qos for each
                    for client, qos in additional_matches:
                        if client not in matches or qos > matches[client]:
                            matches[client] = qos
                return matches




        def add_client(self, qos, uid):
            assert isinstance(qos, int)
            assert isinstance(uid, str)
            assert (0x80 != qos) # SUBACK value for Failure is 0x80
            # TODO broker might want to forward subscription with other qos now; i don't care
            self._subs[uid] = qos

        def remove_client(self, uid):
            del self._subs[uid]

        def is_empty(self):
            return bool(self._subs)

    def __init__(self):
        super().__init__()
        self._subscriptions = dict()

    def add(self, mask, engine, qos, uid):
        assert isinstance(mask, str)
        #assert isinstance(engine, _sre.SRE_Pattern)
        assert isinstance(qos, int)
        assert isinstance(uid, str)

        if mask in self._subscriptions:
            # subscription should have been forwarded already
            assert isinstance(self._subscriptions[mask], self._SubMaskTrackerEntry)
            self._subscriptions[mask].add_client(qos, uid)
            return

        # new management entry
        self._subscriptions[mask] = self._SubMaskTrackerEntry(engine)
        self._subscriptions[mask].add_client(qos, uid)

        raise BeginTracking

    def remove(self, mask, uid):
        assert isinstance(mask, str)
        assert isinstance(uid, str)

        self._subscriptions[mask].remove_client(uid)
        if self._subscriptions[mask].is_empty():
            raise EndTracking

    def matching_masks(self, topicname): # FIXME don't ask, tell what to do!
        """
        FIXME write proper description:
        this method should be called when there is a new topic announced,
        in order to find early subscribers for it.
        :param topicname: a plain topic name (not containing wildcards)
        :return: set of subscribed masks
        """
        assert ('+' not in topicname)
        assert ('#' not in topicname)
        # TODO find and return matching masks (with uids?)
        raise NotImplementedError