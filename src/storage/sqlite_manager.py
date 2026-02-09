"""SQLite database manager for local power measurement storage."""

import sqlite3
import logging
from pathlib import Path
from typing import Optional
from datetime import datetime

from models.power_measurement import PowerMeasurement


logger = logging.getLogger(__name__)


class SQLiteManager:
    """
    Manages SQLite database for storing 200ms power measurements.
    
    Features:
    - WAL mode for concurrent reads/writes
    - Automatic schema creation
    - Index on timestamp for fast queries
    - Auto-vacuum for maintenance
    """
    
    def __init__(self, db_path: str = "data/power_measurements.db"):
        """
        Initialize SQLite manager.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.connection: Optional[sqlite3.Connection] = None
        
        # Ensure data directory exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    
    def connect(self) -> None:
        """Open database connection and initialize schema."""
        try:
            self.connection = sqlite3.connect(
                self.db_path,
                check_same_thread=False,  # Allow use from multiple threads
                timeout=10.0  # Wait up to 10 seconds if database is locked
            )
            
            # Enable WAL mode for better concurrent access
            self.connection.execute("PRAGMA journal_mode=WAL")
            
            # Enable auto-vacuum to prevent database bloat
            self.connection.execute("PRAGMA auto_vacuum=INCREMENTAL")
            
            # Initialize schema
            self._create_tables()
            
            logger.info(f"Connected to SQLite database: {self.db_path}")
            
        except sqlite3.Error as e:
            logger.error(f"Failed to connect to database: {e}")
            raise
    
    def _create_tables(self) -> None:
        """Create database schema if it doesn't exist."""
        schema = """
        CREATE TABLE IF NOT EXISTS power_measurements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            
            -- RMS values
            v_rms REAL NOT NULL,
            i_rms REAL NOT NULL,
            
            -- Power components
            P REAL NOT NULL,
            Q REAL NOT NULL,
            S REAL NOT NULL,
            PF REAL NOT NULL,
            
            -- Harmonic distortion
            v_thd REAL NOT NULL,
            i_thd REAL NOT NULL,
            
            -- Fundamental component
            v1_amp REAL NOT NULL,
            i1_amp REAL NOT NULL,
            phase_diff_deg REAL NOT NULL,
            DPF REAL NOT NULL,
            
            -- Power quality indicators
            crest_factor_v REAL NOT NULL,
            crest_factor_i REAL NOT NULL,
            voltage_deviation_pct REAL NOT NULL,
            k_factor REAL NOT NULL,
            
            -- CPC components
            cpc_distortion_factor REAL NOT NULL,
            cpc_active_current REAL NOT NULL,
            cpc_reactive_current REAL NOT NULL,
            cpc_scattered_current REAL NOT NULL,
            cpc_generated_current REAL NOT NULL,
            cpc_active_ratio REAL NOT NULL,
            cpc_reactive_ratio REAL NOT NULL,
            cpc_scattered_ratio REAL NOT NULL,
            cpc_generated_ratio REAL NOT NULL,
            cpc_reactive_power REAL NOT NULL,
            cpc_scattered_power REAL NOT NULL,
            cpc_generated_power REAL NOT NULL,
            
            -- Frequency and metadata
            frequency REAL NOT NULL DEFAULT 50.0,
            vref_mv INTEGER NOT NULL DEFAULT 3300
        );
        
        -- Index on timestamp for fast time-range queries
        CREATE INDEX IF NOT EXISTS idx_timestamp ON power_measurements(timestamp);
        """
        
        try:
            self.connection.executescript(schema)
            self.connection.commit()
            logger.info("Database schema initialized")
        except sqlite3.Error as e:
            logger.error(f"Failed to create schema: {e}")
            raise
    
    def insert(self, measurement: PowerMeasurement) -> None:
        """
        Insert a single 200ms measurement into the database.
        
        Args:
            measurement: PowerMeasurement object to insert
        """
        query = """
        INSERT INTO power_measurements (
            timestamp, v_rms, i_rms, P, Q, S, PF,
            v_thd, i_thd, v1_amp, i1_amp, phase_diff_deg, DPF,
            crest_factor_v, crest_factor_i, voltage_deviation_pct, k_factor,
            cpc_distortion_factor, cpc_active_current, cpc_reactive_current, 
            cpc_scattered_current, cpc_generated_current,
            cpc_active_ratio, cpc_reactive_ratio, cpc_scattered_ratio, cpc_generated_ratio,
            cpc_reactive_power, cpc_scattered_power, cpc_generated_power, 
            frequency, vref_mv
        ) VALUES (
            ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?,
            ?, ?, ?, ?, ?,
            ?, ?, ?, ?,
            ?, ?, ?, ?, ?
        )
        """
        
        values = (
            measurement.timestamp.isoformat(),
            measurement.v_rms,
            measurement.i_rms,
            measurement.P,
            measurement.Q,
            measurement.S,
            measurement.PF,
            measurement.v_thd,
            measurement.i_thd,
            measurement.v1_amp,
            measurement.i1_amp,
            measurement.phase_diff_deg,
            measurement.DPF,
            measurement.crest_factor_v,
            measurement.crest_factor_i,
            measurement.voltage_deviation_pct,
            measurement.k_factor,
            measurement.cpc_distortion_factor,
            measurement.cpc_active_current,
            measurement.cpc_reactive_current,
            measurement.cpc_scattered_current,
            measurement.cpc_generated_current,
            measurement.cpc_active_ratio,
            measurement.cpc_reactive_ratio,
            measurement.cpc_scattered_ratio,
            measurement.cpc_generated_ratio,
            measurement.cpc_reactive_power,
            measurement.cpc_scattered_power,
            measurement.cpc_generated_power,
            measurement.frequency,
            measurement.vref_mv,
        )
        
        try:
            cursor = self.connection.cursor()
            cursor.execute(query, values)
            self.connection.commit()
            logger.debug(f"Inserted measurement at {measurement.timestamp}")
        except sqlite3.Error as e:
            logger.error(f"Failed to insert measurement: {e}")
            # Don't raise - we don't want DB errors to crash the receiver
    
    def close(self) -> None:
        """Close database connection."""
        if self.connection:
            self.connection.close()
            logger.info("Database connection closed")
