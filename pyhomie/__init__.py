#!/usr/bin/env python3
from enum import Enum, unique
import isodate
import logging

import paho.mqtt.client


class Topic:

    def __init__(self, id, name, attributes={}):
        self._device = None
        self._id = id
        if hasattr(self, "_attributes"):
            self._attributes["name"] = name
        else:
            self._attributes = {"name": name}
        self._attributes.update(attributes)

    def _on_connect(self, device: "Device"):
        self._device = device
        for key in self._attributes.keys():
            self._publish_attribute(key)

    def _on_disconnect(self):
        self._device = None

    def _publish(self, topic=None, payload=None, qos=1, retain=True):
        if not self.is_connected:
            raise RuntimeError("Cannot publish when device is disconnected")
        if topic is None:
            topic = self._topic
        else:
            topic = f"{self._topic}/{topic}"
        if isinstance(payload, bool):
            payload = "true" if payload else "false"
        self._device.client.publish(topic, str(payload), qos, retain)

    def _publish_attribute(self, key):
        payload = self._attributes[key]
        if isinstance(payload, Enum):
            payload = payload.value
        elif isinstance(payload, list):
            payload = ",".join(payload)
        elif isinstance(payload, dict):
            payload = ",".join(payload.keys())
        self._publish(f"${key}", payload)

    @property
    def _topic(self):
        return f"{self._parent_topic}/{self.id}"

    @property
    def attributes(self):
        return self._attributes

    @property
    def id(self):
        return self._id

    @property
    def is_connected(self):
        return self._device is not None and self._device.state != Device.State.DISCONNECTED

    @property
    def name(self):
        return self._attributes["name"]

    @name.setter
    def name(self, name):
        if not isinstance(name, str):
            raise TypeError("Name must be a string")
        self.update_attribute("name", name)

    def on_connect(self, topic: "Topic"):
        pass

    def on_disconnect(self, topic: "Topic"):
        pass

    def on_message(self, topic: "Topic", msg: paho.mqtt.client.MQTTMessage):
        pass

    def subscribe(self, topic, qos=1):
        if not self.is_connected:
            raise RuntimeError("Cannot subscribe when device is disconnected")
        self._device.client.subscribe(f"{self.topic}/topic", qos)

    def unsubscribe(self, topic):
        if not self.is_connected:
            raise RuntimeError("Cannot unsubscribe when device is disconnected")
        self._device.client.unsubscribe(f"{self.topic}/topic")

    def update_attribute(self, key, value, callback=None):
        if self._device is None:
            self._attributes[key] = value
        device_state = self._device._attributes.get("state", Device.State.DISCONNECTED)
        if device_state == Device.State.DISCONNECTED:
            self._attributes[key] = value
            return
        if device_state in Device.RESTRICTED_STATES:
            self._device._attributes["state"] = Device.State.INIT
            self._device._publish_attribute("state")
        if callback is not None:
            callback(value)
        self._attributes[key] = value
        if device_state in Device.RESTRICTED_STATES:
            self._device._attributes["state"] = device_state
            self._device._publish_attribute("state")


class Device(Topic):

    @unique
    class State(Enum):
        DISCONNECTED = "disconnected"
        INIT = "init"
        READY = "ready"
        SLEEPING = "sleeping"
        LOST = "lost"
        ALERT = "alert"

    RESTRICTED_STATES = [State.READY, State.SLEEPING, State.ALERT] # States where some attributes cannot be changed

    def __init__(self, id, name, nodes=[], extensions=[], implementation=None, attributes={}, root_topic="homie"):
        self._attributes = {"homie": "4.0.0"}
        super().__init__(id, name)
        self._attributes["state"] = Device.State.DISCONNECTED
        self._attributes["nodes"] = {}
        self._attributes.update(attributes)
        for node in nodes:
            self._attributes["nodes"][node.id] = node
        self._attributes["extensions"] = extensions
        if implementation is not None:
            self._attributes["implementation"] = implementation
        self._parent_topic = root_topic
        self._client = paho.mqtt.client.Client()

    def _on_connect(self, client, userdata, flags, rc):
        if rc != 0:
            raise RuntimeError("Connection to MQTT broker failed")
        self._attributes["state"] = Device.State.INIT
        super()._on_connect(self)
        for node in self.nodes.values():
            node._on_connect(self)
        self.client.subscribe(self.root_topic + "/$broadcast/#")
        self.on_connect(self)
        self.update_attribute("state", Device.State.READY)

    def _on_disconnect(self, client, userdata, rc):
        for node in self.nodes.values():
            node._on_disconnect()
        self.on_disconnect(self)

    def _on_message(self, client: paho.mqtt.client.Client, userdata, msg: paho.mqtt.client.MQTTMessage):
        if msg.topic.startswith(self.root_topic + "/$broadcast/"):
            msg.topic = msg.topic[len(self.root_topic + "/$broadcast/"):].encode("utf-8")
            self.on_broadcast(self, msg)
            return
        elif not msg.topic.startswith(self._topic + "/"):
            return
        msg.topic = msg.topic[len(self._topic) + 1:].encode("utf-8")
        try:
            offset = msg.topic.index("/")
        except ValueError:
            offset = None
        node_id = msg.topic[:offset]
        if node_id in self.nodes:
            node_msg = msg
            node_msg.topic = msg.topic[len(node_id) + 1:].encode("utf-8")
            self.nodes[target_node]._on_message(node_msg)
        self.on_message(self, msg)

    @property
    def client(self):
        return self._client

    def connect(self, host, port=1883, keepalive=60, bind_address=""):
        if self.state != Device.State.DISCONNECTED:
            raise RuntimeError("Device is already connected")
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect
        self.client.will_set(f"{self._topic}/$state", Device.State.LOST.value, qos=1, retain=True)
        self.client.connect(host, port, keepalive, bind_address)
        self.client.loop_start()

    def disconnect(self):
        self.update_attribute("state", Device.State.DISCONNECTED)
        self.client.disconnect()

    @property
    def extensions(self):
        return self._extensions

    @extensions.setter
    def extensions(self, extensions=[]):
        if not isinstance(extensions, list):
            raise TypeError("Extensions must be a list")
        self._update_attribute("extensions", extensions)

    @property
    def homie_version(self):
        return self._attributes["homie"]

    @property
    def implementation(self):
        return self._implementation

    @implementation.setter
    def implementation(self, implementation):
        if not isinstance(implemetation, str):
            raise TypeError("Implementation must be a string")
        self.update_attribute("implementation", implementation)

    @property
    def nodes(self):
        return self._attributes.get("nodes", {})

    def on_broadcast(self, device: "Device", msg: paho.mqtt.client.MQTTMessage):
        pass

    @property
    def root_topic(self):
        return self._parent_topic

    @property
    def state(self):
        return self._attributes.get("state")

    @state.setter
    def state(self, state: "Device.State"):
        self._attributes["state"] = state
        self._publish_attribute("state")


class Node(Topic):

    def __init__(self, id, name, type, properties=[], attributes={}):
        defined_attributes = {"type": type, "properties": {}}
        defined_attributes.update(attributes)
        super().__init__(id, name, defined_attributes)
        for property in properties:
            self._attributes["properties"][property.id] = property

    def _on_connect(self, device: Device):
        self._parent_topic = device._topic
        super()._on_connect(device)
        for property in self.properties.values():
            property._on_connect(self)
        self.on_connect(self)

    def _on_disconnect(self):
        for property in self.properties.values():
            property._on_disconnect()
        super()._on_disconnect()
        self.on_disconnect(self)

    def _on_message(self, msg: paho.mqtt.client.MQTTMessage):
        try:
            offset = msg.topic.index("/")
        except ValueError:
            offset = None
        property_id = msg.topic[:offset]
        if property_id in self.properties:
            property_msg = msg
            property_msg.topic = msg.topic[len(property_id) + 1:].encode("utf-8")
            self.properties[property_id]._on_message(property_msg)
        self.on_message(self, msg)

    @property
    def properties(self):
        return self._attributes.get("properties", {})

    @property
    def type(self):
        return self._attributes["type"]

    @type.setter
    def type(self, type):
        self.update_attribute("type", type)


class Property(Topic):

    def __init__(self, id, name, datatype, value=None, format=None, settable=False, retained=True, unit=None, attributes={}):
        self._node = None
        defined_attributes = {
            "datatype": datatype,
            "value": value,
            "format": format,
            "settable": bool(settable),
            "retained": bool(retained),
            "unit": unit
        }
        defined_attributes.update(attributes)
        super().__init__(id, name, defined_attributes)
        self._value = value

    def _on_connect(self, node: "Node"):
        self._node = node
        self._parent_topic = node._topic
        super()._on_connect(node._device)
        if self.settable is not None and self.settable:
            self.subscribe("set")
        self._publish_value()
        self.on_connect(self)

    def _on_disconnect(self):
        self._node = None
        super()._on_disconnect()
        self.on_disconnect(self)

    def _on_message(self, msg: paho.mqtt.client.MQTTMessage):
        if self.settable and msg.topic == "set":
            self._on_set(self._parse(msg.payload.decode()))
        self.on_message(self, msg)

    def _on_set(self, value):
        self.value = value
        self.on_set(self)

    def _parse(self, s: str):
        # Cast to data type, reverse of byte casting in paho.mqtt.client.Client.publish()
        if self.datatype == "integer":
            value = int(s)
        elif self.datatype == "float":
            value = float(s)
        elif self.datatype == "boolean":
            value = s == "true"
        elif self.datatype == "string":
            value = s
        elif self.datatype == "enum":
            value = s
        elif self.datatype == "color":
            value = s
        elif self.datatype == "datetime":
            value = isodate.parse_datetime(s)
        elif self.datatype == "duration":
            value = isodate.parse_duration(s)
        else: # Non-standard
            value = s.encode()
        return value

    def _publish_value(self):
        payload = self.value
        if payload is not None:
            if self.datatype == "boolean":
                payload = "true" if payload else "false"
            elif self.datatype == "datetime":
                payload = payload.isoformat()
            elif self.datatype == "duration":
                payload = "P{}DT{}S".format(payload.days, payload.seconds)
        self._publish(None, payload, retain=self.retained)

    @property
    def datatype(self):
        return self._attributes["datatype"]

    @datatype.setter
    def datatype(self, datatype):
        self.update_attribute("datatype", datatype)

    @property
    def format(self):
        return self._attributes["format"]

    @format.setter
    def format(self, format):
        self.update_attribute("format", format)

    @property
    def node(self):
        return self._node

    def on_set(self, property: "Property"):
        pass

    @property
    def retained(self):
        return self._attributes["retained"]

    @retained.setter
    def retained(self, retained):
        self.update_attribute("retained", retained)

    @property
    def settable(self):
        return self._attributes["settable"]

    @settable.setter
    def settable(self, settable):
        self.update_attribute("settable", settable, self._on_settable)

    def _on_settable(self, settable):
        if self.settable and not settable:
            self.unsubscribe("set")
        if not self.settable and settable:
            self.subscribe("set")

    @property
    def unit(self):
        return self._attributes["unit"]

    @unit.setter
    def unit(self, unit):
        self.update_attribute("unit", unit)

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, value):
        if self.value != value:
            # TODO: Validate values
            self._value = value
            if self._device.state != Device.State.DISCONNECTED:
                self._publish_value()
