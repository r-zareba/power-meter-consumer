# Grafana Dashboards Setup

## Quick Start

### 1. Start Grafana
```bash
docker compose -f docker-compose.grafana.yml up -d
```

### 2. Access Grafana
- URL: http://localhost:3000
- Username: `admin`
- Password: `admin` (you'll be prompted to change it on first login)

### 3. View Dashboards
Click on "Dashboards" in the left menu. You'll find three pre-configured dashboards:

1. **Power Meter - Overview**
   - Power components (P, Q, S) over time
   - Power factor gauge and trend
   - Voltage & current RMS
   - Frequency monitoring
   - Phase difference

2. **Power Quality - THD & Harmonics**
   - Voltage THD over time
   - Current THD over time
   - Current THD/Voltage THD gauges
   - Crest factors (V & I)
   - Voltage deviation from nominal
   - Harmonic power responsibility (IEEE 519)

3. **CPC Analysis - Czarnecki's Theory**
   - CPC current components stacked (Ia, Ir, Is, Ig)
   - Current composition pie chart
   - Active current ratio gauge
   - Distortion factor gauge
   - CPC ratios (λ values) over time

## Configuration

### InfluxDB Connection
The datasource is automatically configured to connect to your local InfluxDB at `host.docker.internal:8086`.

If you're running InfluxDB in a Docker container on a network named `power-meter-network`, edit:
```
grafana/provisioning/datasources/influxdb.yml
```
and change the URL to `http://influxdb:8086`

### Dashboard Refresh Rate
All dashboards auto-refresh every 5 seconds. You can change this in the dashboard settings.

### Time Range
Default time range is last 15 minutes. Use the time picker in the top right to change it.

## Customizing Dashboards

1. Open any dashboard
2. Click the gear icon (⚙️) in the top right
3. Make your changes
4. Click "Save dashboard"

Changes persist in the Grafana container volume.

## Stop Grafana
```bash
docker compose -f docker-compose.grafana.yml down
```

## Troubleshooting

### No data showing
1. Check InfluxDB is running and has data:
   ```bash
   influx -database power_meter -execute "SELECT COUNT(*) FROM power_aggregates"
   ```

2. Check Grafana logs:
   ```bash
   docker logs power-meter-grafana
   ```

3. Test datasource in Grafana:
   - Go to Configuration → Data Sources
   - Click "InfluxDB-PowerMeter"
   - Click "Save & Test"

### Can't connect to InfluxDB
- If InfluxDB is on host: URL should be `http://host.docker.internal:8086`
- If InfluxDB is in Docker: URL should be `http://influxdb:8086` or the container name
