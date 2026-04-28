#!/usr/bin/env python3
"""
Wazuh Anomaly Detection with Isolation Forest
Analyzes Wazuh alert logs for anomalies using unsupervised ML

Author: Chas Academy Lab
Date: 2026-04-28
"""

import json
import sys
import os
from pathlib import Path
import logging
from datetime import datetime, timedelta

import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class WazuhAnomalyDetector:
    """Detects anomalies in Wazuh alert data using Isolation Forest"""
    
    def __init__(self, contamination=0.05):
        """
        Initialize the anomaly detector
        
        Args:
            contamination: Expected proportion of anomalies (0-1)
        """
        self.contamination = contamination
        self.model = None
        self.scaler = StandardScaler()
        self.features = None
        
    def load_alerts(self, filepath):
        """Load Wazuh alerts from JSON file"""
        try:
            with open(filepath, 'r') as f:
                alerts = [json.loads(line) for line in f if line.strip()]
            logger.info(f"Loaded {len(alerts)} alerts from {filepath}")
            return alerts
        except FileNotFoundError:
            logger.error(f"File not found: {filepath}")
            return []
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            return []
    
    def extract_features(self, alerts):
        """Extract numerical features from alerts for ML analysis"""
        features_list = []
        
        for alert in alerts:
            try:
                # Extract timestamp
                timestamp = alert.get('timestamp', '')
                
                # Extract rule level and ID
                rule_level = alert.get('rule', {}).get('level', 0)
                rule_id = alert.get('rule', {}).get('id', 0)
                
                # Count matched groups
                groups = alert.get('rule', {}).get('groups', [])
                num_groups = len(groups)
                
                # Check for critical keywords
                has_critical_words = int(
                    any(word in alert.get('full_log', '').lower() 
                    for word in ['failed', 'error', 'denied', 'unauthorized', 'attack'])
                )
                
                # Extract source/destination if available
                decoder = alert.get('decoder', {})
                has_network_data = int('srcip' in decoder or 'dstip' in decoder)
                
                features_list.append({
                    'rule_level': rule_level,
                    'rule_id': rule_id,
                    'num_groups': num_groups,
                    'has_critical_words': has_critical_words,
                    'has_network_data': has_network_data,
                    'alert': alert
                })
                
            except Exception as e:
                logger.warning(f"Error processing alert: {e}")
                continue
        
        return pd.DataFrame(features_list) if features_list else pd.DataFrame()
    
    def train(self, dataframe):
        """Train the Isolation Forest model"""
        if dataframe.empty:
            logger.error("Cannot train on empty dataframe")
            return False
        
        # Select feature columns (exclude 'alert' column)
        feature_cols = [col for col in dataframe.columns if col != 'alert']
        X = dataframe[feature_cols].fillna(0)
        
        # Normalize features
        X_scaled = self.scaler.fit_transform(X)
        
        # Train Isolation Forest
        self.model = IsolationForest(
            contamination=self.contamination,
            random_state=42,
            n_estimators=100
        )
        self.model.fit(X_scaled)
        
        logger.info("Model trained successfully")
        return True
    
    def detect_anomalies(self, dataframe):
        """Detect anomalies in the dataframe"""
        if self.model is None:
            logger.error("Model not trained yet")
            return []
        
        feature_cols = [col for col in dataframe.columns if col != 'alert']
        X = dataframe[feature_cols].fillna(0)
        X_scaled = self.scaler.transform(X)
        
        # Get predictions and anomaly scores
        predictions = self.model.predict(X_scaled)
        scores = self.model.score_samples(X_scaled)
        
        # Add results to dataframe
        dataframe['anomaly'] = predictions
        dataframe['anomaly_score'] = scores
        
        # Extract anomalies
        anomalies = []
        for idx, row in dataframe[dataframe['anomaly'] == -1].iterrows():
            anomalies.append({
                'alert': row['alert'],
                'score': row['anomaly_score'],
                'rule_level': row['rule_level'],
                'rule_id': row['rule_id']
            })
        
        # Sort by anomaly score (lower = more anomalous)
        anomalies.sort(key=lambda x: x['score'])
        
        logger.info(f"Detected {len(anomalies)} anomalies")
        return anomalies
    
    def generate_report(self, anomalies, output_file='anomaly_report.json'):
        """Generate a report of detected anomalies"""
        report = {
            'timestamp': datetime.now().isoformat(),
            'total_anomalies': len(anomalies),
            'anomalies': []
        }
        
        for anomaly in anomalies:
            report['anomalies'].append({
                'alert_timestamp': anomaly['alert'].get('timestamp'),
                'rule_id': anomaly['rule_id'],
                'rule_level': anomaly['rule_level'],
                'anomaly_score': float(anomaly['score']),
                'description': anomaly['alert'].get('rule', {}).get('description'),
                'full_log': anomaly['alert'].get('full_log', '')
            })
        
        # Write report
        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"Report saved to {output_file}")
        return report


def main():
    """Main execution function"""
    if len(sys.argv) < 2:
        print("Usage: python3 anomaly_detector.py <alerts_file> [contamination]")
        print("Example: python3 anomaly_detector.py alerts.json 0.05")
        sys.exit(1)
    
    alerts_file = sys.argv[1]
    contamination = float(sys.argv[2]) if len(sys.argv) > 2 else 0.05
    
    logger.info(f"Starting Wazuh Anomaly Detection")
    logger.info(f"Alerts file: {alerts_file}")
    logger.info(f"Contamination threshold: {contamination}")
    
    # Initialize detector
    detector = WazuhAnomalyDetector(contamination=contamination)
    
    # Load alerts
    alerts = detector.load_alerts(alerts_file)
    if not alerts:
        logger.error("No alerts loaded")
        sys.exit(1)
    
    # Extract features
    df = detector.extract_features(alerts)
    if df.empty:
        logger.error("No features extracted")
        sys.exit(1)
    
    logger.info(f"Extracted features from {len(df)} alerts")
    logger.info(f"Feature statistics:\n{df.describe()}")
    
    # Train model
    detector.train(df)
    
    # Detect anomalies
    anomalies = detector.detect_anomalies(df)
    
    # Generate report
    report = detector.generate_report(anomalies)
    
    # Print summary
    print("\n" + "="*60)
    print("ANOMALY DETECTION REPORT")
    print("="*60)
    print(f"Total alerts analyzed: {len(alerts)}")
    print(f"Anomalies detected: {len(anomalies)}")
    print(f"Detection rate: {len(anomalies)/len(alerts)*100:.2f}%")
    print("\nTop 5 Most Anomalous Alerts:")
    print("-"*60)
    
    for i, anomaly in enumerate(anomalies[:5], 1):
        alert = anomaly['alert']
        print(f"\n{i}. Rule ID: {anomaly['rule_id']} (Level: {anomaly['rule_level']})")
        print(f"   Score: {anomaly['score']:.4f}")
        print(f"   Description: {alert.get('rule', {}).get('description', 'N/A')}")
        print(f"   Timestamp: {alert.get('timestamp', 'N/A')}")
    
    print("\n" + "="*60)
    print(f"Full report saved to: anomaly_report.json")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
