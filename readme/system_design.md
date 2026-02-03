# System Design - Industrial Power Monitoring Architecture

## Overview

This document outlines the industry-standard architecture for power quality monitoring systems, based on IEC 61000-4-30 Class A requirements and practices from commercial products like Fluke 435, Schneider PM8000, and Siemens PAC.

---

## Data Flow Architecture

### Measurement Windows
- **200ms window** - IEC 61000-4-7 standard for 50Hz grids (10 cycles)
- **Sampling rate** - 10.26 kHz continuous ADC sampling
- **Measurement frequency** - Calculate metrics every 200ms (5 times/second)

### Storage Tiers

**Local Database (Raspberry Pi - SQLite)**
- **Granularity:** 200ms (full resolution)
- **Data stored:** ALL raw measurements (V_rms, I_rms, P, Q, S, PF, THD, harmonics, frequency)
- **Purpose:** IEC compliance, forensic analysis, regulatory requirements
- **Retention:** 30-90 days
- **Write frequency:** Every 200ms (INSERT immediately)
- **Storage size:** ~1 GB per month

**Cloud TimeSeries Database (InfluxDB/TimescaleDB)**
- **Granularity:** 1 second (statistical aggregates)
- **Data stored:** Aggregated statistics from 5 × 200ms measurements (avg, min, max, std)
- **Purpose:** Long-term analytics, dashboards, trend analysis
- **Retention:** 1-3 years
- **Upload frequency:** Batched every 10 seconds (10 aggregates per upload)
- **Storage size:** ~10 MB per month (80% reduction vs raw data)

**MQTT Stream (Real-time)**
- **Granularity:** 1 second (ephemeral)
- **Data published:** 1-second aggregates
- **Purpose:** Live monitoring, real-time alerts, ML services
- **Retention:** 0 seconds (publish/subscribe pattern, not stored)
- **Publish frequency:** Every 1 second (QoS 1 for reliability)

---

## Why This Architecture?

### Network Efficiency
- **Bandwidth savings:** 80% reduction (1 aggregate/sec vs 5 measurements/sec)
- **Upload operations:** 5x fewer cloud writes (reduces CPU and queue pressure)
- **Cloud storage cost:** 100x reduction vs uploading raw samples

### Queue Stability
- **Arrival rate:** 1 item/second to upload queues (vs 5/second without aggregation)
- **Service rate:** Single worker at 150ms/upload handles 6.7 uploads/sec
- **Utilization:** 15% (very safe) vs 75% without aggregation

### IEC Compliance
- **Full data preservation:** All 200ms measurements stored locally as required
- **Forensic capability:** Can investigate any event with full resolution
- **No data loss:** Local database survives internet outages

---

## Implementation Phases

### Phase 1: Standard Industrial Architecture (Recommended)
**Status:** Most practical for 90% of use cases

**Architecture:**
- Calculate power metrics every 200ms (V_rms, I_rms, P, Q, S, PF, THD, harmonics)
- Store ALL 200ms metrics in local SQLite database
- Aggregate 5 measurements into 1-second statistics (avg, min, max, std)
- Publish 1-second aggregates to MQTT (for real-time consumers)
- Batch upload 1-second aggregates to cloud InfluxDB (every 10 seconds)

**Suitable for:**
- Real-time dashboards and monitoring
- Power quality compliance reporting
- Load forecasting and optimization
- Energy billing and cost analysis
- Standard anomaly detection
- 90% of ML applications (forecasting, pattern detection, efficiency optimization)

### Phase 2: Advanced ML Support (If Needed)
**Status:** Optional, for specialized applications

**Additional capabilities:**
- Also upload 200ms metrics to cloud (separate measurement)
- Use InfluxDB retention policies (keep 200ms for 7 days, aggregates forever)
- ML services can query either granularity depending on task
- Data size: ~50 MB/day (still 30x less than raw samples)

**Suitable for:**
- Appliance disaggregation (NILM)
- Motor health monitoring
- Detailed power quality pattern recognition
- Advanced harmonic analysis
- Specialized waveform ML models

### Phase 3: On-Demand Raw Data (Specialized)
**Status:** Only for research or advanced diagnostics

**Additional capabilities:**
- Keep raw ADC waveforms only on Pi (not continuous cloud upload)
- Provide API endpoint for requesting specific time windows
- ML service requests: "Send raw waveforms from 14:30:00 to 14:35:00"
- Upload only when needed, not streaming

**Suitable for:**
- Deep learning on waveform shapes
- Research and algorithm development
- Transient event analysis
- Forensic investigation of specific incidents

---

## Event Handling Exception

**Critical events are sent immediately at full 200ms resolution:**
- Voltage sags/swells (< 207V or > 253V)
- Overvoltage/undervoltage conditions
- High THD violations (> 8%)
- Frequency deviations
- Power outages

Events bypass normal aggregation and trigger:
- Immediate cloud storage at 200ms resolution
- Real-time MQTT alerts (QoS 1)
- Detailed forensic data for investigation

---

## Real-Time Requirements

**IEC 61850 Real-Time Classes:**
- **Class 1:** < 1 second (alerts, notifications) ✅ Achieved
- **Class 2:** < 100ms (monitoring, control) ✅ Possible with MQTT
- **Class 3:** < 10ms (protection relays) ❌ Requires hardware
- **Class 4:** < 3ms (critical protection) ❌ Hardware only

**This system targets Class 1-2**, which is appropriate for power quality monitoring and standard industrial applications.

---

## Machine Learning Considerations

### Feature Engineering Already Complete
The calculated 200ms metrics (RMS, power, THD, harmonics) ARE the ML features. Raw ADC samples are rarely needed.

### ML Data Requirements by Task
**Works with 1-second aggregates (Phase 1):**
- Load forecasting and demand prediction
- Energy optimization and cost reduction
- Macro-level anomaly detection
- Billing predictions and analytics
- Standard power quality monitoring

**Requires 200ms metrics (Phase 2):**
- Appliance signature recognition (NILM)
- Motor bearing fault detection
- Detailed harmonic pattern analysis
- Power quality event classification

**Requires raw waveforms (Phase 3):**
- Deep learning on waveform shapes (rare)
- Transient event research
- Arc fault detection (specialized)
- Academic studies and R&D

---

## Bandwidth and Cost Comparison

**Option A: Send all raw samples continuously**
- Data: 5 × 1024 samples × 2 channels × 2 bytes = 20 KB/sec
- Monthly: ~50 GB
- Cost: $5-25/month + egress fees
- Bandwidth: ~160 kbps continuous

**Option B: Send 1-second aggregates (Phase 1)**
- Data: 15 fields × 8 bytes = 120 bytes/sec
- Monthly: ~300 MB
- Cost: ~$0.10/month
- Bandwidth: ~1 kbps

**Difference: 170x reduction in bandwidth and cost**

---

## Industry Standards Alignment

This architecture matches commercial power quality analyzers:

| Aspect | Industry Standard | This System |
|--------|------------------|-------------|
| Measurement window | 200ms (IEC 61000-4-7) | ✅ 200ms |
| Local storage | Full resolution | ✅ All 200ms data |
| Cloud storage | Aggregated | ✅ 1-second statistics |
| Real-time publish | 0.5-1 second | ✅ 1 second |
| Cloud batch upload | 5-10 seconds | ✅ 10 seconds |
| IEC reports | 10-minute aggregates | ✅ Supported |
| Event resolution | Full (200ms or better) | ✅ 200ms immediate |

**Reference implementations:** Fluke 435, Schneider PM8000, Siemens PAC, Hioki PW3198, Dranetz HDPQ

---

## Recommendations

**Start with Phase 1** - It covers 90% of industrial use cases and matches industry standards.

**Add Phase 2** only if you specifically need:
- Appliance-level disaggregation
- Motor health monitoring
- Specialized harmonic analysis ML

**Use Phase 3** only for:
- Research and development
- Algorithm validation
- Specific forensic investigations (on-demand, not continuous)

The tiered approach provides maximum flexibility while maintaining efficiency and compliance.
