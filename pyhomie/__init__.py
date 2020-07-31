#!/usr/bin/env python3

# TODOs
# =====
# * More type checking and value validation
# * Better exception handling
# * Developer guide
# * Test suite

from enum import Enum, unique
import isodate
import logging
import paho.mqtt.client


class Device:

    @unique
    class State(Enum):
        DISCONNECTED = "disconnected"
        INIT = "init"
        READY = "ready"
        SLEEPING = "sleeping"
        ALERT = "alert"

    RESTRICTED_STATES = [State.READY, State.SLEEPING, State.ALERT] # States where some attributes cannot be changed

    def __init__(self, id, name, nodes=[], extensions=[], implementation=None, root_topic="homie"):
        self._id = id
        self._homie_version = "4.0.0"
        self._name = name
        self._state = Device.State.DISCONNECTED
        self._nodes = {}
        self._nodes_init = {}
        for node in nodes:
            self._nodes_init[node.id] = node
        self._extensions = extensions
        self._implementation = implementation
        self._root_topic = root_topic
        self._client = paho.mqtt.client.Client()

    def add_node(self, node: "Node"):
        if not isinstance(node, Node):
            raise TypeError("Node must be a Node")
        state = self.state
        if state == Device.State.DISCONNECTED:
            self._nodes_init[node.id] = node
            return
        if node.id in self._nodes:
            raise RuntimeError("Node [{}] already exists.".format(node.id))
        if state in Device.RESTRICTED_STATES:
            self.state = Device.State.INIT
        self._nodes[node.id] = node
        node._on_connect(self)
        self.publish("$nodes", ",".join(self.nodes.keys()))
        if state in Device.RESTRICTED_STATES:
            self.state = state

    @property
    def client(self):
        return self._client

    def connect(self, host, port=1883, keepalive=60, bind_address=""):
        if self.state != Device.State.DISCONNECTED:
            raise RuntimeError("Device is already connected")
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect
        self.client.will_set(self.topic + "/$state", "lost", qos=1, retain=True)
        self.client.connect(host, port, keepalive, bind_address)
        self.client.loop_start()

    def disconnect(self):
        self.state = Device.State.DISCONNECTED
        self.client.disconnect()

    @property
    def extensions(self):
        return self._extensions

    @extensions.setter
    def extensions(self, extensions=[]):
        if not isinstance(extensions, list):
            raise TypeError("Extensions must be a list")
        state = self.state
        if state in Device.RESTRICTED_STATES:
            self.state = Device.State.INIT
        self._extensions = extensions
        self.publish("$extensions", ",".join(self.extensions))
        if state in Device.RESTRICTED_STATES:
            self.state = state

    @property
    def homie_version(self):
        return self._homie_version

    @property
    def id(self):
        return self._id

    @property
    def implementation(self):
        return self._implementation

    @implementation.setter
    def implementation(self, implementation):
        if not isinstance(implemetation, str):
            raise TypeError("Implementation must be a string")
        state = self.state
        if state in Device.RESTRICTED_STATES:
            self.state = Device.State.INIT
        self._implementation = implementation
        self.publish("$implementation", self.implementation)
        if state in Device.RESTRICTED_STATES:
            self.state = state

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, name):
        if not isinstance(name, str):
            raise TypeError("Name must be a string")
        self._name = name
        self.publish("$name", self.name)

    @property
    def nodes(self):
        if self.state == Device.State.DISCONNECTED:
            return self._nodes_init
        return self._nodes

    def on_broadcast(self, device: "Device", msg: paho.mqtt.client.MQTTMessage):
        pass

    def _on_connect(self, client, userdata, flags, rc):
        if rc != 0:
            raise RuntimeError("Connection to MQTT broker failed")
        self.client.subscribe(self.root_topic + "/$broadcast/#")
        self.state = Device.State.INIT
        if self.implementation is not None:
            self.implementation = self.implementation
        self.publish("$nodes")
        for node in self._nodes_init.values():
            self.add_node(node)
        self.extensions = self.extensions
        self.name = self.name
        self.publish("$homie", self.homie_version)
        self.on_connect(self)

    def on_connect(self, device):
        pass

    def _on_disconnect(self, client, userdata, rc):
        self._state = Device.State.DISCONNECTED
        self._nodes_init = self._nodes
        for node in self.nodes.values():
            node._on_disconnect()
        self._nodes = {}
        self.on_disconnect(self)

    def on_disconnect(self, device):
        pass

    def _on_message(self, client: paho.mqtt.client.Client, userdata, msg: paho.mqtt.client.MQTTMessage):
        if msg.topic.startswith(self.root_topic + "/$broadcast/"):
            msg.topic = msg.topic[len(self.root_topic + "/$broadcast/"):].encode("utf-8")
            self.on_broadcast(self, msg)
            return
        elif not msg.topic.startswith(self.topic + "/"):
            return
        msg.topic = msg.topic[len(self.topic) + 1:].encode("utf-8")
        try:
            offset = msg.topic.index("/")
        except ValueError:
            offset = None
        target_node = msg.topic[:offset]
        if target_node in self.nodes:
            node_msg = msg
            node_msg.topic = msg.topic[len(target_node) + 1:].encode("utf-8")
            self.nodes[target_node]._on_message(node_msg)
        self.on_message(self, msg)

    def on_message(self, device: "Device", msg: paho.mqtt.client.MQTTMessage):
        pass

    def publish(self, topic="", payload=None, qos=1, retain=True):
        if self.state == Device.State.DISCONNECTED:
            raise RuntimeError("Device cannot publish when disconnected")
        self.client.publish(self.topic + "/" + topic, payload, qos, retain)

    def remove_node(self, node_id):
        state = self.state
        if state == Device.State.DISCONNECTED:
            if node_id not in self._nodes_init:
                raise KeyError("Node ID [{}] not in nodes".format(node_id))
            node = self._nodes_init[node_id]
            del self._nodes_init[node_id]
            return node
        if node_id not in self.nodes:
            raise KeyError("Node ID [{}] not in nodes".format(node_id))
        if state in Device.RESTRICTED_STATES:
            self.state = Device.State.INIT
        node = self.nodes[node_id]
        node._on_disconnect()
        del self._nodes[node_id]
        if state in Device.RESTRICTED_STATES:
            self.state = state
        return node

    @property
    def root_topic(self):
        return self._root_topic

    @property
    def state(self):
        return self._state

    @state.setter
    def state(self, state: "Device.State"):
        self._state = Device.State(state)
        self.publish("$state", self.state.value)

    def subscribe(self, topic, qos=1):
        if self.state == Device.State.DISCONNECTED:
            raise RuntimeError("Device cannot subscribe when disconnected")
        self.client.subscribe(self.topic + "/" + topic, qos)

    @property
    def topic(self):
        return self.root_topic + "/" + self.id

    def unsubscribe(self, topic):
        if self.state == State.DISCONNECTED:
            raise RuntimeError("Device cannot unsubscribe when disconnected")
        self.client.unsubscribe(self.topic + "/" + topic)


class Node:

    def __init__(self, id, name, type, properties=[]):
        self._id = id
        self._name = name
        self._type = type
        self._properties = {}
        self._properties_init = {}
        for property in properties:
            self._properties_init[property.id] = property
        self._device = None

    def add_property(self, property: "Property"):
        if not isinstance(property, Property):
            raise TypeError("Property must be a Property")
        state = self.state
        if state == Device.State.DISCONNECTED:
            self._properties_init[property.id] = property
            return
        if property.id in self._properties:
            raise RuntimeError("Property [{}] already exists.".format(property.id))
        if state in Device.RESTRICTED_STATES:
            self.state = Device.State.INIT
        self._properties[property.id] = property
        property._on_connect(self)
        state = self.state
        self.publish("$properties", ",".join(self.properties.keys()))
        if state in Device.RESTRICTED_STATES:
            self.state = state

    def connect(self, device: Device):
        device.add_node(self)

    @property
    def device(self):
        return self._device

    def disconnect(self):
        self.device.remove_node(self.id)

    @property
    def id(self):
        return self._id

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, name):
        if not isinstance(name, str):
            raise TypeError("Name must be a string")
        self._name = name
        self.publish("$name", self.name)

    def _on_connect(self, device: Device):
        self._device = device
        self.name = self.name
        self.type = self.type
        self.publish("$properties")
        for property in self._properties_init.values():
            self.add_property(property)
        self.on_connect(self)

    def on_connect(self, node):
        pass

    def _on_disconnect(self):
        properties = self.properties
        for property in self.properties.values():
            property._on_disconnect()
        self._properties_init = properties
        self._properties = {}
        self._device = None
        self.on_disconnect(self)

    def on_disconnect(self, node):
        pass

    def _on_message(self, msg: paho.mqtt.client.MQTTMessage):
        try:
            offset = msg.topic.index("/")
        except ValueError:
            offset = None
        target_property = msg.topic[:offset]
        if target_property in self.properties:
            property_msg = msg
            property_msg.topic = msg.topic[len(target_property) + 1:].encode("utf-8")
            self.properties[target_property]._on_message(property_msg)
        self.on_message(self, msg)

    def on_message(self, node: "Node", msg: paho.mqtt.client.MQTTMessage):
        pass

    @property
    def properties(self):
        if self.state == Device.State.DISCONNECTED:
            return self._properties_init
        return self._properties

    def publish(self, topic, payload=None, qos=1, retain=True):
        if self.device is None:
            raise RuntimeError("Node cannot publish before being added to a Device")
        self.device.publish(self.id + "/" + topic, payload, qos, retain)

    def remove_property(property_id):
        state = self.state
        if state == Device.State.DISCONNECTED:
            if property_id not in self._properties_init:
                raise KeyError("Property ID [{}] not in properties".format(property_id))
            property = self._properties_init[property_id]
            del self._properties_init[property_id]
            return property
        if property_id not in self.properties:
            raise KeyError("Property ID [{}] not in properties".format(property_id))
        if state in Device.RESTRICTED_STATES:
            self.state = Device.State.INIT
        property = self.properties[property_id]
        property._on_disconnect()
        del self._properties[property_id]
        self.publish("$properties", ",".join(self.properties.keys()))
        if state in Device.RESTRICTED_STATES:
            self.state = state
        return property

    def subscribe(self, topic, qos=1):
        if self.device is None:
            raise RuntimeError("Node cannot subscribe before being added to a Device")
        self.device.subscribe(self.id + "/" + topic, qos)

    @property
    def state(self):
        if self.device is None:
            return Device.State.DISCONNECTED
        return self.device.state

    @state.setter
    def state(self, state):
        self.device.state = state

    @property
    def type(self):
        return self._type

    @type.setter
    def type(self, type):
        if not isinstance(type, str):
            raise TypeError("Type must be a string")
        self._type = type
        self.publish("$type", self.type)

    def unsubscribe(self, topic):
        if self.device is None:
            raise RuntimeError("Node cannot unsubscribe before being added to a Device")
        self.device.unsubscribe(self.id + "/" + topic)


class Property:

    def __init__(self, id, name, data_type, value=None, format=None, settable=False, retained=True, unit=None):
        self._id = id
        self._name = name
        self._data_type = data_type
        self._value = value
        self._format = format
        self._settable = bool(settable)
        self._retained = bool(retained)
        self._unit = str(unit)
        self._node = None

    def connect(self, node):
        node.add_property(self)

    @property
    def data_type(self):
        return self._data_type

    @data_type.setter
    def data_type(self, data_type):
        state = self.state
        if state in Device.RESTRICTED_STATES:
            self.state = Device.State.INIT
        self._data_type = data_type
        self.publish("$datatype", self.data_type)
        if state in Device.RESTRICTED_STATES:
            self.state = state

    def disconnect(self):
        self.node.remove_property(self.id)

    @property
    def format(self):
        return self._format

    @format.setter
    def format(self, format):
        state = self.state
        if state in Device.RESTRICTED_STATES:
            self.state = Device.State.INIT
        self._format = format
        self.publish("$format", self.format)
        if state in Device.RESTRICTED_STATES:
            self.state = state

    @property
    def id(self):
        return self._id

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, name):
        self._name = name
        self.publish("$name", self.name)

    @property
    def node(self):
        return self._node

    def _on_connect(self, node):
        self._node = node
        self.name = self.name
        self.data_type = self.data_type
        if self.format is not None:
            self.format = self.format
        if self.settable is not None:
            self.settable = self.settable
            if self.settable:
                self.subscribe("set")
        if self.retained is not None:
            self.retained = self.retained
        if self.unit is not None:
            self.unit = self.unit
        if self.value is not None:
            self.value = self.value

    def _on_disconnect(self):
        self._node = None
        self.on_disconnect(self)

    def on_disconnect(self, property):
        pass

    def _on_message(self, msg: paho.mqtt.client.MQTTMessage):
        if msg.topic == "set":
            # Cast to data type, reverse of byte casting in paho.mqtt.client.Client.publish()
            if self.data_type == "integer":
                self.value = int(msg.payload.decode("utf-8"))
            elif self.data_type == "float":
                self.value = float(msg.payload.decode("utf-8"))
            elif self.data_type == "boolean":
                self.value = msg.payload.decode("utf-8") == "true"
            elif self.data_type == "string":
                self.value = msg.payload.decode("utf-8")
            elif self.data_type == "enum":
                self.value = msg.payload.decode("utf-8")
            elif self.data_type == "color":
                self.value = msg.payload.decode("utf-8")
            elif self.data_type == "datetime":
                self.value = isodate.parse_datetime(msg.payload.decode("utf-8"))
            elif self.data_type == "duration":
                self.value = isodate.parse_duration(msg.payload.decode("utf-8"))
            elif isinstance(self.value, (bytes, bytearray)): # Non-standard
                self.value = msg.payload
        self.on_message(self, msg)

    def on_message(self, property: "Property", msg: paho.mqtt.client.MQTTMessage):
        pass

    def publish(self, topic="", payload=None):
        if self.node is None:
            raise RuntimeError("Property cannot publish before being added to a Node")
        if topic == "":
            payload = self.value
            if payload is not None:
                if self.data_type == "boolean":
                    payload = "true" if payload else "false"
                elif self.data_type == "datetime":
                    payload = payload.isoformat()
                elif self.data_type == "duration":
                    payload = "P{}DT{}S".format(payload.days, payload.seconds)
            self.node.publish(self.id, payload, retain=self.retained)
        else:
            self.node.publish(self.id + "/" + topic, payload)

    @property
    def retained(self):
        return self._retained

    @retained.setter
    def retained(self, retained):
        state = self.state
        if state in Device.RESTRICTED_STATES:
            self.state = Device.State.INIT
        self._retained = retained
        self.publish("$retained", "true" if self.retained else "false")
        if state in Device.RESTRICTED_STATES:
            self.state = state

    @property
    def settable(self):
        return self._settable

    @settable.setter
    def settable(self, settable):
        state = self.state
        if state in Device.RESTRICTED_STATES:
            self.state = Device.State.INIT
        self._settable = settable
        self.publish("$settable", "true" if self.settable else "false")
        if state in Device.RESTRICTED_STATES:
            self.state = state

    @property
    def state(self):
        if self.node is None:
            return Device.State.DISCONNECTED
        return self.node.state

    @state.setter
    def state(self, state):
        self.node.state = state

    def subscribe(self, topic, qos=1):
        if self.node is None:
            raise RuntimeError("Property cannot subscribe before being added to a Node")
        self.node.subscribe(self.id + "/" + topic, qos)

    @property
    def unit(self):
        return self._unit

    @unit.setter
    def unit(self, unit):
        state = self.state
        if state in Device.RESTRICTED_STATES:
            self.state = Device.State.INIT
        self._unit = unit
        self.publish("$unit", self.unit)
        if state in Device.RESTRICTED_STATES:
            self.state = state

    def unsubscribe(self, topic):
        if self.node is None:
            raise RuntimeError("Property cannot unsubscribe before being added to a Node")
        self.node.unsubscribe(self.id + "/" + topic)

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, value):
        if self.value != value:
            # TODO: Validate values
            self._value = value
        self.publish()
