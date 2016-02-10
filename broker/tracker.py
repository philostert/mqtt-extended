from broker.exceptions import BeginTracking, EndTracking
from broker.client import MQTTClient
from broker.util import MQTTUtils
import re
from abc import ABCMeta, abstractmethod


# Two basic alternatives "one-topic-level" and "at-least-two-topic-levels" in order to not match empty strings.
# Per level literal character group %(l)s excludes certain unicode points.
# Unicode exclusions defined @ MQTT Version 3.1.1, Section 1.5.3 UTF-8 encoded strings.
re_match_valid_mask = re.compile(r'^([+#]|%(l)s+)$|^(([+]|%(l)s*)/(([+]|%(l)s*)/)*([+#]|%(l)s*))$' %
                                 {'l': r'[^+#/\u0000\ud800-\udfff\u0001-\u001f\u007f-\u009f]'}) #group: allowed literals

re_match_valid_topic_literal = re.compile(r'^(%(l)s+|/)+$' %
                                 {'l': r'[^+#/\u0000\ud800-\udfff\u0001-\u001f\u007f-\u009f]'}) #group: allowed literals

# TODO and then changes all methods like get_all_...() and print() which can be more straight forward then.

class Tracker(metaclass=ABCMeta):
    def __init__(self):
        self._tree = self._TreeNode.root_node()

    class _TreeNode:
        '''Tree with has Depth-First-Search iterator. Nodes per level are unordered (uses dict).'''

        @classmethod
        def root_node(cls):
            node = cls('ROOT')
            node.path = None
            return node

        def __init__(self, path):
            assert isinstance(path, str)
            self.levels = dict()
            self.path = path # dummy root node shall have None

        class _BasicIter:
            def __init__(self, node, path_constraint=None, use_wildcards=True):
                '''
                bidirectional wildcards: may be in 'path' as well as in 'path_constraint' but mutally exclusive!
                :param node:
                :param path_constraint:
                :param use_wildcards: wildcards are bidirectional when used
                :return:
                '''
                assert isinstance(node, Tracker._TreeNode)
                assert isinstance(path_constraint, str) if path_constraint else True
                assert isinstance(use_wildcards, bool)

                if path_constraint is None:
                    self._path_constraint = None
                    self._stack = [node]
                else:
                    self._path_constraint = path_constraint.split('/')
                    self._use_wildcards   = use_wildcards
                    self._depth = 0
                    self._constraint_len  = len(self._path_constraint)
                    #self._wildcard_depth  = 0 # FIXME
                    if node.path: # not root node
                        self._depth = node.path.count('/') +1
                        #raise NotImplementedError("iterators from any node currently not supported, expecting root node")
                        # FIXME might have wildcards and therefore fine: assert (node.path == path_constraint[:len(node.path)])
                        # FIXME some inputs are really bad and should raise Exceptions
                    self._stack = [(node, self._depth)]

            def __iter__(self):
                # in order to only include nodes below: handle first level now
                self.__next__()
                return self

            def follow(self, key):
                if key in self._node.levels:
                    self._stack.append((self._node.levels[key], self._holding_depth + 1))

            def __next__(self):
#                print("BEGIN stack", self._stack)
                if not self._stack:
                    raise StopIteration
                if self._path_constraint is None:
                    node = self._stack.pop()
                    for n in node.levels.values():
                        self._stack.append(n)
                    return node
                else:
                    self._node, self._holding_depth = self._stack.pop()
                    key_constraint = self._path_constraint[self._holding_depth] if self._holding_depth < self._constraint_len else 'KAK' # FIXME KAK
#                    print("key_constraint %d/%d  \"%s\"" % (self._holding_depth, self._constraint_len-1, key_constraint))
#                    print("node.path", self._node.path)
                    if self._use_wildcards:
                        # XXX bidirectional wildcards: may be in 'path' as well as in 'path_constraint' but mutually exclusive!

                        # 1) check for wildcards in node.path and follow them
                        # even though 'key_constraint' is 'abc' from topic/abc/foo the following
                        # subscriptions topic/+/foo and topic/# shall match
                        self.follow('+')
                        self.follow('#')

                        # 2) check for wildcards in path_constraint
                        # basically matching each topic against one subscription mask. each topic would be in node.path
                        if key_constraint in {'+', '#'}:    # match this whole level
                            for n in self._node.levels.values():
                                self._stack.append((n, self._holding_depth +1))
                        else:                               # match literal only
                            self.follow(key_constraint)
                    else:
                        self.follow(key_constraint)
                    return self._node

        def __iter__(self):
            return self._BasicIter(self) # default iterator gets all

        def iterator(self, node, path_constraint=None, use_wildcards=True):
            return self._BasicIter(node, path_constraint, use_wildcards)

        def add_here(self, key):
            assert isinstance(key, str)
            if self.path:
                path = "%s/%s" % (self.path, key)
            else:
                path = key
            new = self.__class__(path) # new element
            self.levels[key] = new
            return new

        def relative_node(self, relative_path, create=False):
            '''
            Walks the tree (but never upwards) and retrieves node.
            Raises Exception KeyError if 'path' not found within tree and 'create' is False
            :param relative_path: caution: every empty level string '' or in '/topic' or in 'a//b' is a step!
            :param create: creates new nodes while walking
            :return: node
            '''
            assert isinstance(relative_path, str)
            path_levels = relative_path.split("/")
            parent = self
            for key in path_levels:
                if key in parent.levels:
                    parent = parent.levels[key]
                else:
                    if not create:
                        path = key if not parent.path else "%s/%s" % (parent.path, key)
                        raise KeyError("Node does not exist: %s" % path)
                    parent = parent.add_here(key) # create
            return parent # == new created leaf now


class TopicTracker(Tracker):
    class _TreeNode(Tracker._TreeNode):
        def __init__(self, path):
            super().__init__(path)
            self.origin = None

    class _TopicIterator:
        def __init__(self, node, match_mask=None):
            assert isinstance(node, TopicTracker._TreeNode)
            # get a tree node iterator
            self.tree_iter = TopicTracker._TreeNode._BasicIter(node, match_mask)

        def __iter__(self):
            return self

        def __next__(self):
            # skip non-topic nodes, which are just necessary for data structure
            while True:
                # Exception StopIteration is not caught on purpose
                node = self.tree_iter.__next__()
                if node.origin: # found topic
                    return node.path, node.origin

    def __init__(self):
        super().__init__()

    def __iter__(self): # XXX Hack, this allows to do such as "for ... in topic_tracker"
        return self.iterator()

    def iterator(self):
        return self._TopicIterator(self._tree)

    def match_mask_iterator(self, match_mask):
        assert isinstance(match_mask, str)
        if not re_match_valid_mask.match(match_mask):
            raise ValueError
        return self._TopicIterator(self._tree, match_mask)

    def _iterator_by_node(self, node):
        assert isinstance(node, self._TreeNode)
        return self._TopicIterator(node)

    def add_topic(self, topic, origin):
        '''
        :param topic: literal topic
        :param origin: client uid
        :return:
        '''
        assert isinstance(topic, str)
        assert isinstance(origin, str)

        print("self._tree is of type:", type(self._tree))
        assert isinstance(self._tree, self._TreeNode)

        if not re_match_valid_topic_literal.match(topic):
            raise ValueError("Corrupted topic.")

        # create path if necessary
        target = self._tree.relative_node(topic, create=True)
        if not bool(target.origin):
            target.origin = origin
            raise BeginTracking("first Announcement: %s" % topic)
        else:
            target.origin = origin # just update origin

    def get_matching_topics(self, mask):
        '''
        Uses graph Depth-First-Search algorithm to find and collect
        matching announced topics. Together with origin client's uid.
        Each topic only appears once.
        :param mask:
        :return:
        '''
        raise DeprecationWarning('use match_mask_iterator !')
        assert isinstance(mask, str)
        if not re_match_valid_mask.match(mask):
            raise ValueError

        matches = {}

        mask_levels = mask.split("/")
        mask_len = len(mask_levels)
        node_stack = [(self._tree, 0, '')] #== [(node, depth, path)]
        while node_stack:
            node, depth, path = node_stack.pop()
            if depth == mask_len: # insert self and stop this route if last mask level
                if node.origin:
                    matches[path[1:]] = node.origin
                continue

            # walk 0,1..n nodes per level depending on wildcards and availability.
            mask_key = mask_levels[depth]
            if mask_key == '#': # every topic below is a match
                #matches.update(self._get_all_topics_below(node, path))
                for t,uid in self._iterator_by_node(node):
                    matches[t] = uid
            elif mask_key == '+': # walk all child nodes, nothing is decided yet
                for tk,n in node.levels.items():
                    node_stack.append((n, depth+1, "%s/%s" % (path, tk)))
            else: # mask_key is literal topic key, walk this node if it exists
                if mask_key in node.levels:
                    node_stack.append((node.levels[mask_key], depth+1, "%s/%s" % (path, mask_key)))

        """
        matches = {}
        ereg = MQTTUtils.convert_to_ereg(mask)
        engine = re.compile(ereg)
        topics = self.get_all_topics()
        for t, o in self.get_iterator():
            if engine.match(t):
                matches[t] = o
        """
        return matches

    def print(self):
        for t, o in self.iterator():
            print ("topic \"%s\"   provided by \"%s\"" % (t, o))

# FIXME don't ask, tell! Let the tracker also do publication forwards?!
class SubMaskTracker(Tracker):
    class _TreeNode(Tracker._TreeNode):
        def __init__(self, path):
            super().__init__(path)
            self.subscriptions = dict()
            # TODO change to full_path and for all tracker classes initialized in super().__init__(path)

        def is_empty(self):
            return bool (not self.levels and not self.subscriptions)

        def has_subscriptions(self):
            return bool (self.subscriptions)

    class _SubscriptionIterator:
        def __init__(self, node, topic):
            assert isinstance(node, SubMaskTracker._TreeNode)
            # get a tree node iterator
            self.tree_iter = node.iterator(node, topic)

        def __iter__(self):
            self.node_subscriptions_iterator = None
            self.node_path = None
            return self

        def __next__(self):
            # Iterator of _TreeNode will raise StopIteration
            while True:
                # before switching nodes, handle all subscriptions of this node
                if self.node_subscriptions_iterator:
                    #assert isinstance(self.node_subscriptions_iterator, IteratorFOOOO)
                    try:
                        uid,qos = self.node_subscriptions_iterator.__next__()
                        return self.node_path, qos, uid
                    except (StopIteration):
                        self.node_subscriptions_iterator = None
                        self.node_path = None
                # Exception StopIteration is not caught on purpose
                node = self.tree_iter.__next__()
                if node.has_subscriptions():
                    self.node_subscriptions_iterator = node.subscriptions.items().__iter__()# TODO
                    self.node_path = node.path

    def subscription_iterator(self, topic=None):
        startnode = self._tree
        return self._SubscriptionIterator(startnode, topic)

    def __init__(self):
        super().__init__()
        assert isinstance(self._tree, self._TreeNode)
        #self._subscriptions = dict()
        #self._tree # attributes .levels .path

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


        target_node = self._tree.relative_node(mask, create=True)
        # TODO target_node = self._get_target_level_node(mask, create=True)
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
            target_node = self._tree.relative_node(mask)
            del target_node.subscriptions[client]
            if not target_node.has_subscriptions():
                raise EndTracking
        except (KeyError):
            pass # ignore if subscription was not there

    def _merge_subscriptions_into(self, collection, addition):
        for client, qos in addition.items():
            if client not in collection or qos > collection[client]:
                collection[client] = qos

    def _get_matching_nodes (self, topic): # TODO iterate_matching_nodes(topic)
        raise NotImplementedError
        pass
    def get_subscriptions(self, topic):# TODO get_subscriptions -> get_matching_nodes (self, topic) for easier different tasks
        '''
        Uses graph Depth-First-Search algorithm to find and collect matching subscriptions. Each
        client only appears once with it's maximum of granted QoS.
        Raises ValueError for invalid topics.
        :param topic:
        :return:
        '''
        assert isinstance(topic, str)
        if not re_match_valid_topic_literal.match(topic):
            raise ValueError

        # mapping of subscriptions found
        collected = type(self._tree.subscriptions)()

        publish_topic_levels = topic.split("/")
        final_depth = len(publish_topic_levels)-1
        node_stack = [(self._tree, 0)] #== [(node, holding_depth)]
        while node_stack:
            node, holding_depth = node_stack.pop()
            # searching at most three sub-nodes: the literal, '+' and '#'
            avail_sub_nodes = [ (key, node.levels[key]) for key in {'#', '+', publish_topic_levels[holding_depth]} if key in node.levels ]
            for key, sub_node in avail_sub_nodes:
                assert isinstance(sub_node, self._TreeNode)
                if key == '#' or holding_depth == final_depth:
                    # no need to look any deeper there, get subscriptions
                    self._merge_subscriptions_into(collected, sub_node.subscriptions) # TODO insert mask/path because i need it!
                else:
                    node_stack.append((sub_node, holding_depth +1))
        return collected

    def print(self):
        for node in self._tree:
            for uid, qos in node.subscriptions.items():
                print ("(print all) Subscription: %d \"%s\"  (by %s)" % (qos, node.path, uid))