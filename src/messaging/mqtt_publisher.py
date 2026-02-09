"""MQTT publisher for 1-second aggregate data."""

import logging
from typing import Optional
import paho.mqtt.client as mqtt

from models.mqtt_message import AggregateMessage


logger = logging.getLogger(__name__)


class MQTTPublisher:
    """
    Publishes 1-second aggregate power measurements via MQTT.
    
    Features:
    - QoS 1 for reliable delivery
    - Automatic reconnection
    - Topic structure: power_meter/{device_id}/metrics/1s
    """
    
    def __init__(
        self,
        broker_host: str,
        broker_port: int,
        device_id: str,
        topic_prefix: str
    ):
        """
        Initialize MQTT publisher.
        
        Args:
            broker_host: MQTT broker hostname or IP
            broker_port: MQTT broker port
            device_id: Unique device identifier
            topic_prefix: Topic prefix for all messages
        """
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.device_id = device_id
        self.topic_prefix = topic_prefix
        
        self.client: Optional[mqtt.Client] = None
        self.connected = False
        
        # Topic for 1-second aggregates
        self.topic_1s = f"{topic_prefix}/{device_id}/metrics/1s"
    
    def connect(self) -> None:
        """Connect to MQTT broker."""
        try:
            # Create MQTT client
            self.client = mqtt.Client(client_id=f"{self.device_id}_publisher")
            
            # Set callbacks
            self.client.on_connect = self._on_connect
            self.client.on_disconnect = self._on_disconnect
            
            # Connect to broker
            self.client.connect(self.broker_host, self.broker_port, keepalive=60)
            
            # Start network loop in background thread
            self.client.loop_start()
            
            logger.info(f"Connecting to MQTT broker at {self.broker_host}:{self.broker_port}")
            
        except Exception as e:
            logger.error(f"Failed to connect to MQTT broker: {e}")
            raise
    
    def _on_connect(self, client, userdata, flags, rc):
        """Callback when connected to broker."""
        if rc == 0:
            self.connected = True
            logger.info(f"Connected to MQTT broker (topic: {self.topic_1s})")
        else:
            self.connected = False
            logger.error(f"Failed to connect to MQTT broker, return code: {rc}")
    
    def _on_disconnect(self, client, userdata, rc):
        """Callback when disconnected from broker."""
        self.connected = False
        if rc != 0:
            logger.warning(f"Unexpected MQTT disconnection, return code: {rc}")
        else:
            logger.info("Disconnected from MQTT broker")
    
    def publish(self, message: AggregateMessage) -> bool:
        """
        Publish 1-second aggregate message.
        
        Args:
            message: AggregateMessage to publish
            
        Returns:
            True if published successfully, False otherwise
        """
        if not self.client or not self.connected:
            logger.warning("Cannot publish: not connected to MQTT broker")
            return False
        
        try:
            payload = message.to_json()
            result = self.client.publish(
                topic=self.topic_1s,
                payload=payload,
                qos=1,  # QoS 1: At least once delivery
                retain=False  # Don't retain (this is streaming data)
            )
            
            # Check if publish was queued successfully
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.debug(f"Published aggregate at {message.timestamp}")
                return True
            else:
                logger.error(f"Failed to publish: {result.rc}")
                return False
                
        except Exception as e:
            logger.error(f"Exception during publish: {e}")
            return False
    
    def disconnect(self) -> None:
        """Disconnect from MQTT broker."""
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
            logger.info("MQTT publisher disconnected")
