from broker.exceptions import BeginTracking, EndTracking

class Tracker:
    def __init__(self):
        pass


class TopicTracker(Tracker):
    def __init__(self):
        super().__init__()

# FIXME don't ask, tell! Let the tracker also do forwarding decisions and their execution?!
class SubMaskTracker(Tracker):
    class _SubMaskTrackerEntry:
        def __init__(self, engine):
            self._engine = engine
            self._subs = dict()

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