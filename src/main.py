import sys

import paho.mqtt.client as mqtt

MQTT_BROKER = "192.168.1.8"
MQTT_PORT = 1883
MQTT_TOPIC = "esp32/power"


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Connected to MQTT Broker!")
        client.subscribe(MQTT_TOPIC)
        print(f"Subscribed to topic: {MQTT_TOPIC}")
    else:
        print(f"Failed to connect, return code {rc}")


def on_disconnect(client, userdata, rc):
    if rc != 0:
        print("Unexpected disconnection from MQTT broker")
    else:
        print("Disconnected from MQTT broker")


def on_message(client, userdata, msg):
    print(f" [x] Received message on {msg.topic}: {msg.payload.decode()}")


def main():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="")
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message

    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
    except Exception as e:
        print(f"Could not connect to MQTT broker: {e}")
        sys.exit(1)

    print(" [*] Waiting for messages. To exit press CTRL+C")
    try:
        client.loop_forever()
    except KeyboardInterrupt:
        print("Interrupted")
        sys.exit(0)


if __name__ == "__main__":
    main()
