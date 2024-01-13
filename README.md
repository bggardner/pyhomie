# pyhomie
A simple and extensible Python implementation of [The Homie Convention](https://github.com/homieiot/convention).

# Installation
```
git clone https://github.com/bggardner/pyhomie.git
cd pyhomie
sudo pip3 install .
```

# Usage
`pyhomie` uses the [paho-mqtt](https://github.com/eclipse/paho.mqtt.python) module, so its usage is very similar.
## Example
```
#!/usr/bin/env python3
import pyhomie
from time import sleep

def on_connect(device: pyhomie.Device):
    # Executed after Homie Device initialization
    # Can be used to start sensor threads that write to property values
    # Upon return, the Homie Device will enter the "ready" state
    pass

property = pyhomie.Property("property-id", "Example Property", "int")
node = pyhomie.Node("node-id", "Example Node", [property])
device = pyhomie.Device("device-id", "Example Device", [node])
device.on_connect = on_connect
# Optional, set MQTT client username/password
device.client.username_pw_set("username", "password")
device.connect("mqtt-broker")

# Alternative to using on_connect()
while True:
    sleep(1)
    if device.state != pyhomie.Device.State.READY:
        continue
    property.value += 1
```
## API
`pyhomie` contains three classes that represent a Homie topology, all inheriting the `Topic` abstract base class: `Device`, `Node`, and `Property`

### Topic (inherited by Device, Node, and Property

#### Methods
`on_connect(device)` User-defined callback; called when the `Device` connects to the MQTT broker, or when a `Node` or `Property` is added
* `device` (`Device`) Object instance for using inside callback

`on_disconnect(device)` User-defined callback; called when the `Devices` disconnects from the MQTT broker, or when a `Node` or `Property` is removed
* `device` (`Device`) Object instance for using inside callback

`on_message(device, msg)` User-defined callback; called when a message is received with a topic at or below the object's position in the topic hierarchy
* `obj` (`Topic`) `pyhomie` `Topic` instance for using inside callback
* `msg` (`paho.mqtt.client.MQTTMessage`) Message with the topic *relative* to the object ("property-id" instead of "homie/device-id/node-id/property-id", e.g.)

`subscribe(topic, qos=1)` Subscribe to the *relative* topic, otherwise same as `paho.mqtt.client.Client.subscribe()`
By default, subscriptions are made to the Homie broadcast topic and to the `set` topics of settable properties.

`unsubscribe(topic)` Unsubscribe to the *relative* topic, otherwise same as `paho.mqtt.client.Client.subscribe()`

`update_attribute(key, value, callback=None)` Add or update a Homie attribute. Device will enter the "init" state, publish the change, then enter the "ready" state
* `key` (str) Homie Attribute ID, without the "$". CAUTION: Do not use pre-defined keys such as `id`, `name`, etc.
* `value` (...) Attribute value, typically a simple data type (str, int, float, bool)
* `callback` (Callable) User-defined callback; called after the device enters the "init" state, but before the attribute is updated/published

#### Properties
`attributes` (dict, read-only) List of Homie Attributes of the instance.

`id` (str, read-only) Homie ID used in the topic tree, provided to the constructor

`is_connected` (bool, read-only) `True` if the device has connected to the MQTT broker

`name` (str) Homie `$name` attribute

### Device
`Device(id, name, nodes=[], implementation=None, attributes={}, root_topic="homie")` constructor
* `id` (str) Homie device ID [A-Za-z0-9\-]
* `name` (str) Homie device `$name` attribute 
* `nodes` (list[`Node`]) Initial list of the device's nodes; `Node.id`s become the Homie `$nodes` attribute
* `implementation` (str) Homie device `$implementation` attribute
* `attributes` (dict) Home device attributes. CAUTION: Will overwrite matching attributes such as `$id`, `$name`, etc.
* `root_topic` (str) Homie root topic [A-Za-z0-9\-]

#### Methods
`connect(host, port=1883, keepalive=60, bind_address="")` Connects to MQTT broker, same parameters as `paho.mqtt.client.Client.connect()`

`disconnect()` Disconnects from the broker; same as `paho.mqtt.client.Client.disconnect()`

`on_broadcast(device, msg)` User-defined callback; called when a Homie `$broadcast` message is received
* `device` (`Device`) Device instance for using inside callback
* `msg` (`paho.mqtt.client.MQTTMessage`) Broadcast message with the *relative* topic (i.e. with root topic and "/$broadcast/" removed)

#### Properties
`class State(Enum)`
* `DISCONNECTED` Not connected to the MQTT broker
* `INIT` Publishing changes to restricted attributes
* `READY` normal operation, must be set by the user
* `SLEEPING` and `ALERT` must be set by the user

`client` (`paho.mqtt.client.Client`, read-only) The client instance used by the device

`extensions` ([str]) List of extensions in the Homie `$extensions` attribute

`homie_version` (str, read-only) Homie Convention version

`implementation` (str) Homie `$implementation` attribute

`nodes` ([`Node`]) List of `Node` objects whose IDs comprise the Homie `$nodes` attribute

`root_topic` (str, read-only) Homie root topic provided to the constructor

### Node
`Node(id, name, type, properties=[], attributes={})` constructor
* `id` (str) Homie node ID [A-Za-z0-9\-]
* `name` (str) Homie node `$name` attribute 
* `type` (str) Homie node `$type` attribute 
* `properties` ([`Properties`]) List of `Property` object whose IDs comprise the Homie `$properties` attribute
* `attributes` (dict) Home device attributes. CAUTION: Will overwrite matching attributes such as `$id`, `$name`, etc.

#### Properties
`properties` ([`Property`]) List of `Property` objects whose ids comprise the Homie `$properties` attribute

`type` (str) Homie node `$type` attribute

### Property
`Property(id, name, data_type, value=None, format=None, settable=None, retained=None, unit=None)` constructor
* `id` (str) Homie property ID [A-Za-z0-9\-]
* `name` (str) Homie property `$name` attribute
* `data_type` (str) Homie property `$datatype` attribute
* `value` (...) Default value of the property
* `format` (str) Homie property `$format` attribute
* `settable` (bool) Homie property `$settable` attribute
* `retained` (bool) Homie property `$retained` attribute
* `unit` (str) Homie property `$unit` attribute
* `attributes` (dict) Home device attributes. CAUTION: Will overwrite matching attributes such as `$id`, `$name`, etc.

#### Methods
`on_set(property)` User-defined callback; called when the Property's "set" topic value changes
* `property` (Property) New value can be accessed with `property.value`

#### Properties
`datatype` (str) Homie property `$datatype` attribute

`format` (str) Homie property `$format` attribute

`retained` (bool) Homie property `$retained` attribute

`settable` (bool) Homie property `$settable` attribute

`value` (...) Default value of the property
