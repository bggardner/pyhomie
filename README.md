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

def on_connect(device):
    device.state = pyhomie.Device.State.READY

property = pyhomie.Property("property-id", "Example Property", "int")
node = pyhomie.Node("node-id", "Example Node", [property])
device = pyhomie.Device("device-id", "Example Device", [node])
device.on_connect = on_connect
device.connect("mqtt-broker")

while True:
    sleep(1)
    if device.state != pyhomie.Device.State.READY:
        continue
    property.value += 1
```
## API
Homie defines a MQTT topic tree that is hierarchical.
* Root Topic
    * Device ID
        * Node ID
            * Property ID
            
Example: `homie/my-device/my-node/my-property`

`pyhomie` also takes a hierarchical approach with its object classes:
* `paho.mqtt.client.Client`
    * `pyhomie.Device`
        * `pyhomie.Node`
            * `pyhomie.Property`

While the "child" classes do not extend the parent classes, they `connect()` and `disconnect()` to the Homie (MQTT) "network".

By default, the only subscriptions a device makes are to the Homie broadcast topic and to the `set` topics of settable properties.  The user may call the appropriate  `subscribe()` methods to add subscriptions.

All message callbacks are passed the object instance to which they were assigned, as well as the `paho.mqtt.client.MQTTMessage` from the broker, with the topic *relative* to the Homie topic tree.  For example, a broadcast message topic will only contain the subtopic after `$broadcast/`, and an `on_message` assigned to a property may only be called with the *relative* topic `set`.
### Common Methods
`connect(...)` Connects to the parent object; arguments differ by object class

`disconnect()` Disconnects from parent object; same as `paho.mqtt.client.Client.disconnect()`

`on_connect(device)` User-defined callback; called when the object successfully connects to parent object
* `device` (`Device`) Object instance for using inside callback

`on_disconnect(device)` User-defined callback; called when the object successfully connects from parent object
* `device` (`Device`) Object instance for using inside callback

`on_message(device, msg)` User-defined callback; called when a message is received with a topic at or below the object's position in the topic tree
* `obj` (`Device`|`Node`|`Property`) `pyhomie` object instance for using inside callback
* `msg` (`paho.mqtt.client.MQTTMessage`) Message with the topic *relative* to the object

`publish(topic, payload=None, qos=1, retain=True)` Publish to the *relative topic*, otherwise same as `paho.mqtt.client.Client.publish()`

`subscribe(topic, qos=1)` Subscribe to the *relative* topic, otherwise same as `paho.mqtt.client.Client.subscribe()`

`unsubscribe(topic)` Unsubscribe to the *relative* topic, otherwise same as `paho.mqtt.client.Client.subscribe()`
### Common Properties
`id` (str, read-only) Homie ID used in the topic tree, provided to the constructor

`name` (str) Homie `$name` attribute

`state` (`Device.State`) Homie `$state` attribute (string representation in `state.value`)
### Device
`Device(id, name, nodes=[], implementation=None, root_topic="homie")` constructor
* `id` (str) Homie device ID [A-Za-z0-9\-]
* `name` (str) Homie device `$name` attribute 
* `nodes` (list[`Node`]) Initial list of the device's nodes; `Node.id`s become the Homie `$nodes` attribute
* `implementation` (str) Homie device `$implementation` attribute
* `root_topic` (str) Homie root topic [A-Za-z0-9\-]
#### Methods
`add_node(node)` Adds the specified node to the device
* `node` (`Node`) Node to be added

`connect(host, port=1883, keepalive=60, bind_address="")` Connects to MQTT broker, same parameters as `paho.mqtt.client.Client.connect()`

`on_broadcast(device, msg)` User-defined callback; called when a Homie `$broadcast` message is received
* `device` (`Device`) Device instance for using inside callback
* `msg` (`paho.mqtt.client.MQTTMessage`) Broadcast message with the *relative* topic

`remove_node(node_id)` Removes a node from the device, returns the removed `Node` object
* `node_id` (str) ID of the node to be removed
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

`topic` (str, read-only) Fully-qualified MQTT topic
### Node
`Node(id, name, type, properties=[])` constructor
* `id` (str) Homie node ID [A-Za-z0-9\-]
* `name` (str) Homie node `$name` attribute 
* `type` (str) Homie node `$type` attribute 
* `properties` ([`Properties`]) List of `Property` object whose IDs comprise the Homie `$properties` attribute
#### Methods
`add_property(property)` Adds a property to the node
* `property` (`Property`) Property to be added

`connect(device)` Connects to a device
* `device` (`Device`) Device to which to connect

`remove_property(property_id)` Removes a property from the node, returns the removed `Property` object
* `property_id` (str) ID of the property to be removed
#### Properties
`device` (`Device`, read-only) If connected to a device, the device instance, `None` otherwise

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
#### Methods
`connect(node)` Connects to a node
* `node` (`Node`) Node to which to connect


#### Properties
`data_type` (str) Homie property `$datatype` attribute

`format` (str) Homie property `$format` attribute

`node` (`Node`, read-only) If connected to a node, the node instance, `None` otherwise

`retained` (bool) Homie property `$retained` attribute

`settable` (bool) Homie property `$settable` attribute

`value` (...) Default value of the property
