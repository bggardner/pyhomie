#!/usr/bin/env python3

# TODOs
# =====
# * Implement remove_node() and remove_property()
# * Allow changing of device attributes, following device state rules

# Not Implemented
# ===============
# Device states: "sleeping" and "alert" as they seem unnecessary

import isodate
import logging
import paho.mqtt.client

class Client:

    def __init__(self, mqtt_client_id, devices=[], topic="homie"):
        self.connected = False
        self.mqtt_client = paho.mqtt.client.Client(mqtt_client_id)
        self.mqtt_client.on_connect = self._on_connect
        self.mqtt_client.on_message = self._on_message
        self.mqtt_client.on_disconnect = self._on_disconnect
        self._devices = {}
        self._topic = topic
        for device in devices:
            if device.id in self._devices:
                raise RuntimeError("Device [{}] already exists.".format(device.id))
            self.will_set(device.id)
            self._devices[device.id] = device

    def connect(self, host, port=1883, keepalive=60, bind_address=""):
        self.mqtt_client.connect(host, port, keepalive, bind_address)
        self.mqtt_client.loop_start()

    def disconnect(self):
        for device in self.devices.values():
            device.disconnect()
        self.mqtt_client.disconnect()

    @property
    def devices(self):
        return self._devices

    def _on_connect(self, mqtt_client, userdata, flags_dict, rc):
        if rc == 0:
            self.connected = True
        else:
            self.connected = False
            return
        for device in self.devices.values():
            device.connect(self)
        self.on_connect(mqtt_client, userdata, flags_dict, rc)

    def on_connect(self, mqtt_client, userdata, flags_dict, rc):
        pass

    def _on_disconnect(self, mqtt_client, userdata, rc):
        self.connected = False
        self.on_disconnect(mqtt_client, userdata, rc)

    def on_disconnect(self, mqtt_client, userdata, rc):
        pass

    def _on_message(self, client, userdata, msg: paho.mqtt.client.MQTTMessage):
        if msg.topic.startswith(self.topic + "/"):
            msg.topic = msg.topic[len(self.topic) + 1:].encode("utf-8")
            target_device = msg.topic[:msg.topic.index("/")]
            if target_device in self.devices:
                device_msg = msg
                device_msg.topic = msg.topic[len(target_device) + 1:].encode("utf-8")
                self.devices[target_device]._on_message(device_msg)
            self.on_message(msg)

    def on_message(self, msg: paho.mqtt.client.MQTTMessage):
        pass

    def publish(self, topic, payload, qos=1, retain=True):
        if not self.connected:
            logging.error("Cannot publish when disconnected")
        self.mqtt_client.publish(self.topic + "/" + topic, payload, qos, retain)

    def subscribe(self, topic):
        if not self.connected:
            logging.error("Cannot subscribe when disconnected")
        self.mqtt_client.subscribe(self.topic + "/" + topic);

    @property
    def topic(self):
        return self._topic

    def will_set(self, device_id):
        self.mqtt_client.will_set(self.topic + "/" + device_id + "/$state", "lost", qos=1, retain=True)


class Device:

    def __init__(self, id, name, nodes=[], extensions=[], implementation=None):
        self._id = id
        self._homie_version = "4.0.0"
        self._name = name
        self._state = "init"
        self._nodes = {}
        self._nodes_init = nodes
        self._extensions = extensions
        self._implementation = implementation
        self.client = None

    def add_node(self, node):
        if node.id in self._nodes:
            raise RuntimeError("Node [{}] already exists.".format(node.id))
        self._nodes[node.id] = node
        node.connect(self)
        self.publish("$nodes", ",".join(self.nodes.keys()))

    def connect(self, client):
        self.client = client
        self.publish("$homie", self.homie_version)
        self.name = self.name
        self.state = "init"
        self.publish("$nodes", "")
        self.publish("$extensions", ",".join(self.extensions))
        if self.implementation is not None:
            self.publish("$implementation", self.implementation)
        for node in self._nodes_init:
            self.add_node(node)
        self.state = "ready"

    @property
    def connected(self):
        return self.client.connected and self.state != "disconnected"

    def disconnect(self):
        self.state = "disconnected"

    @property
    def extensions(self):
        return self._extensions

    @property
    def homie_version(self):
        return self._homie_version

    @property
    def id(self):
        return self._id

    @property
    def implementation(self):
        return self._implementation

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, name):
        self.publish("$name", name)

    @property
    def nodes(self):
        return self._nodes

    def _on_message(self, msg: paho.mqtt.client.MQTTMessage):
        target_node = msg.topic[:msg.topic.index("/")]
        if target_node in self.nodes:
            node_msg = msg
            node_msg.topic = msg.topic[len(target_node) + 1:].encode("utf-8")
            self.nodes[target_node]._on_message(node_msg)
        self.on_message(msg)

    def on_message(self, msg: paho.mqtt.client.MQTTMessage):
        pass

    def publish(self, topic, payload, qos=1, retain=True):
        if self.client is None:
            raise RuntimeError("Device cannot publish before being added to a Client")
        self.client.publish(self.id + "/" + topic, payload, qos, retain)

    @property
    def state(self):
        return self._state

    @state.setter
    def state(self, state):
        self._state = state
        self.publish("$state", state)

    def subscribe(self, topic):
        if self.client is None:
            raise RuntimeError("Device cannot subscribe before being added to a Client")
        self.client.subscribe(self.id + "/" + topic)


class Node:

    def __init__(self, id, name, type, properties=[]):
        self._id = id
        self._name = name
        self._type = type
        self._properties = {}
        self._properties_init = properties
        self.device = None

    def add_property(self, property):
        if property.id in self._properties:
            raise RuntimeError("Property [{}] already exists.".format(property.id))
        self._properties[property.id] = property
        property.connect(self)
        state = self.device.state
        if state in ["ready", "sleeping", "alert"]:
            self.device.state = "init"
        self.publish("$properties", ",".join(self.properties.keys()))
        if state in ["ready", "sleeping", "alert"]:
            self.device.state = state

    def connect(self, device):
        self.device = device
        self.publish("$name", self.name)
        self.publish("$type", self.type)
        self.publish("$properties", "")
        for property in self._properties_init:
            self.add_property(property)

    @property
    def id(self):
        return self._id

    @property
    def name(self):
        return self._name

    def _on_message(self, msg: paho.mqtt.client.MQTTMessage):
        target_property = msg.topic[:msg.topic.index("/")]
        if target_property in self.properties:
            property_msg = msg
            property_msg.topic = msg.topic[len(target_property) + 1:].encode("utf-8")
            self.properties[target_property]._on_message(property_msg)
        self.on_message(msg)

    def on_message(self, msg: paho.mqtt.client.MQTTMessage):
        pass

    @property
    def properties(self):
        return self._properties

    def publish(self, topic, payload, qos=1, retain=True):
        if self.device is None:
            raise RuntimeError("Node cannot publish before being added to a Device")
        self.device.publish(self.id + "/" + topic, payload, qos, retain)

    def subscribe(self, topic):
        if self.device is None:
            raise RuntimeError("Node cannot subscribe before being added to a Device")
        self.device.subscribe(self.id + "/" + topic)

    @property
    def type(self):
        return self._type


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
        self.node = None

    def connect(self, node):
        self.node = node
        self.publish("$name", self.name)
        self.publish("$datatype", self.data_type)
        if self.format is not None:
            self.publish("$format", self.format)
        if self.settable is not None:
            self.publish("$settable", "true" if self.settable else "false")
            if self.settable:
                self.subscribe("set")
        if self.retained is not None:
            self.publish("$retained", "true" if self.retained else "false")
        if self.unit is not None:
            self.publish("$unit", self.unit)
        if self.value is not None:
            self.value = self.value

    @property
    def data_type(self):
        return self._data_type

    @property
    def format(self):
        return self._format

    @property
    def id(self):
        return self._id

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, name):
        self.publish("$name", name)

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
        self.on_message(msg)

    def on_message(self, msg: paho.mqtt.client.MQTTMessage):
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

    @property
    def settable(self):
        return self._settable

    def subscribe(self, topic):
        if self.node is None:
            raise RuntimeError("Property cannot subscribe before being added to a Node")
        self.node.subscribe(self.id + "/" + topic)

    @property
    def unit(self):
        return self._unit

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, value):
        if self.value != value:
            # TODO: Validate values
            self._value = value
            self.publish()
