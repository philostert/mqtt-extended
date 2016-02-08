from broker.exceptions import BeginTracking, EndTracking
from broker.client import MQTTClient
import re

# Two basic alternatives "one-topic-level" and "at-least-two-topic-levels" in order to not match empty strings.
# Per level literal character group %(l)s excludes certain unicode points.
# Unicode exclusions defined @ MQTT Version 3.1.1, Section 1.5.3 UTF-8 encoded strings.
re_match_valid_mask = re.compile(r'^([+#]|%(l)s+)$|^(([+]|%(l)s*)/(([+]|%(l)s*)/)*([+#]|%(l)s*))$' %
                                 {'l': r'[^+#/\u0000\ud800-\udfff\u0001-\u001f\u007f-\u009f]'}) #group: allowed literals

re_match_valid_topic_literal = re.compile(r'^(%(l)s+|/)+$' %
                                 {'l': r'[^+#/\u0000\ud800-\udfff\u0001-\u001f\u007f-\u009f]'}) #group: allowed literals

class Tracker: # FIXME classify as abstract
    def __init__(self):
        self._level0 = None

    def _get_target_level_node(self, path, create=False):
        '''
        Walks along the tree nodes and retrieves the target level node.
        Raises KeyError if path not found when 'create'==False.
        '''
        assert isinstance(path, str)

        topic_levels = path.split("/")
        node = self._level0
        for key in topic_levels:
            # create sub-level if necessary
            if key not in node.levels:
                if create:
                    node.levels[key] = self._Level()
                else:
                    raise KeyError("Path not found.")
            node = node.levels[key] # move on
        assert isinstance(node, type(self._level0))
        return node # target node found

class TopicTracker(Tracker):
    class _Level:
        def __init__(self):
            self.levels = dict()
            self.origin = None


    def __init__(self):
        super().__init__()
        self._level0 = self._Level()

    def add_topic(self, topic, origin):
        '''
        :param topic: literal topic
        :param origin: client uid
        :return:
        '''
        assert isinstance(topic, str)
        assert isinstance(origin, str)

        if not re_match_valid_topic_literal.match(topic):
            raise ValueError("Corrupted topic.")

        # create path if necessary
        target = self._get_target_level_node(topic, create=True)
        if not bool(target.origin):
            target.origin = origin
            raise BeginTracking("first Announcement: %s" % topic)
        else:
            target.origin = origin # just update origin

    def get_all_topics(self):
        topics = {}

        path = ''
        node_stack = [(self._level0, path)] #== [(node, path)]
        while node_stack:
            node, path = node_stack.pop()
            for k,n in node.levels.items():
                node_stack.append((n, "%s/%s" % (path, k)))
            if node.origin:
                topics[path[1:]] = node.origin
        return topics

    def get_matching_topics(self, mask):
        '''
        Uses graph Depth-First-Search algorithm to find and collect matching announced topics.
        Each topic only appears once.
        :param mask:
        :return:
        '''
        assert isinstance(mask, str)
        if not re_match_valid_mask.match(mask):
            raise ValueError

        matches = {}
        engine = re.compile(mask)
        topics = self.get_all_topics()
        for t, o in topics.items():
            if engine.match(t):
                matches[t] = o
        return matches

    def print(self):
        '''
        print("PRINTING TopicTracker contents:")
        path = ''
        node_stack = [(self._level0, path)] #== [(node, path)]
        while node_stack:
            node, path = node_stack.pop()
            for k,n in node.levels.items():
                node_stack.append((n, "%s/%s" % (path, k)))
            if node.origin:
                print ("Topic: \"%s\"  (origin: %s)" % (path[1:], node.origin))
        '''
        topics = self.get_all_topics()
        for t, o in topics.items():
            print ("Topic: \"%s\"  (origin: %s)" % (t, o))

# FIXME don't ask, tell! Let the tracker also do publication forwards?!
class SubMaskTracker(Tracker):
    class _Level:
        def __init__(self):
            self.levels = dict()
            self.subscriptions = dict()

        def is_empty(self):
            return bool (not self.levels and not self.subscriptions)

        def has_subscriptions(self):
            return bool (self.subscriptions)

    def __init__(self):
        super().__init__()
        self._subscriptions = dict()
        self._level0 = self._Level() # (sublevel, subscribers) # level0 cannot have subscribers, mask would be ''

    def add_subscription(self, mask, qos, client):
        '''
        Adds or updates a subscription mask with the corresponding QoS.
        Raises ValueError for invalid masks.
        :param mask: subscription mask, basically a topic with possible wildcards
        :param qos: Quality of Service
        :param client: client which subscribes topic/mask
        :return:
        '''
        assert isinstance(mask, str)
        assert isinstance(qos, int)
        assert (0x80 != qos) # SUBACK value for Failure is 0x80
        #assert isinstance(client, MQTTClient) TODO use MQTTClient ?
        assert isinstance(client, str) # uid

        if not re_match_valid_mask.match(mask):
            raise ValueError("Corrupted mask.")

        target_node = self._get_target_level_node(mask, create=True)
        # check whether this subscription is the only one for this mask
        first = not target_node.has_subscriptions()
        target_node.subscriptions[client] = qos
        if first:
            raise BeginTracking("first Subscription: %s" % mask)

    def remove_subscription(self, mask, client):
        '''
        Removes a subscription of a client.
        Raises ValueError for invalid masks.
        Raises KeyError if mask not found.
        :param mask: subscription mask, basically a topic with possible wildcards
        :param client:
        :return:
        '''
        assert isinstance(mask, str)
        #assert isinstance(client, MQTTClient) TODO use MQTTClient ?
        assert isinstance(client, str) # uid

        if not re_match_valid_mask.match(mask):
            raise ValueError("Corrupted mask.")

        try:
            target_node = self._get_target_level_node(mask)
            del target_node.subscriptions[client]
            if not target_node.has_subscriptions():
                raise EndTracking
        except (KeyError):
            pass # ignore if subscription was not there

    def _merge_subscriptions_into(self, collection, addition):
        for client, qos in addition.items():
            if client not in collection or qos > collection[client]:
                collection[client] = qos

    def get_subscriptions(self, topic):
        '''
        Uses graph Depth-First-Search algorithm to find and collect matching subscriptions. Each
        client only appears once with it's maximum of granted QoS.
        :param topic:
        :return:
        '''
        assert isinstance(topic, str)
        if not re_match_valid_topic_literal.match(topic):
            raise ValueError

        # mapping of subscriptions found
        collected = type(self._level0.subscriptions)()

        publish_topic_levels = topic.split("/")
        final_depth = len(publish_topic_levels)-1
        node_stack = [(self._level0, 0)] #== [(node, holding_depth)]
        while node_stack:
            node, holding_depth = node_stack.pop()
            # searching at most three sub-nodes: the literal, '+' and '#'
            avail_sub_nodes = [ (key, node.levels[key]) for key in {'#', '+', publish_topic_levels[holding_depth]} if key in node.levels ]
            for key, sub_node in avail_sub_nodes:
                assert isinstance(sub_node, self._Level)
                if key == '#' or holding_depth == final_depth:
                    # no need to look any deeper there, get subscriptions
                    self._merge_subscriptions_into(collected, sub_node.subscriptions)
                else:
                    node_stack.append((sub_node, holding_depth +1))
        return collected

    def print(self):
        path = ''
        node_stack = [(self._level0, path)] #== [(node, path)]
        while node_stack:
            node, path = node_stack.pop()
            # searching at most three sub-nodes: the literal, '+' and '#'
            for k,n in node.levels.items():
                node_stack.append((n, "%s/%s" % (path, k)))
            for uid, qos in node.subscriptions.items():
                print ("SUB: %d \"%s\"  (by %s)" % (qos, path[1:], uid))