#!/bin/bash
# Start and enable Mosquitto, InfluxDB, and Grafana services

echo "Starting and enabling Mosquitto..."
sudo systemctl start mosquitto
sudo systemctl enable mosquitto

echo "Starting and enabling InfluxDB..."
sudo systemctl start influxdb
sudo systemctl enable influxdb

echo "Starting Grafana (Docker)..."
sudo docker compose -f docker-compose.grafana.yml down && sudo docker compose -f docker-compose.grafana.yml up -d

echo "All services started"
echo ""
echo "Service status:"
sudo systemctl status mosquitto --no-pager -l | head -3
sudo systemctl status influxdb --no-pager -l | head -3
echo ""
echo "Grafana: http://localhost:3000 (admin/admin)"
