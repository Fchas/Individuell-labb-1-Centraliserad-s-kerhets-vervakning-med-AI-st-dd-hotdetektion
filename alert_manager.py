#!/usr/bin/env python3
"""
Wazuh AI Alert Manager
Processes anomaly detection results and converts them to actionable alerts

Author: Chas Academy Lab
Date: 2026-04-28
"""

import json
import sys
from datetime import datetime
from enum import Enum
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels"""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class WazuhAlertManager:
    """Manages and prioritizes Wazuh alerts from anomaly detection"""
    
    def __init__(self):
        self.alerts = []
        self.severity_thresholds = {
            'critical': -1.5,      # anomaly_score < -1.5 = critical
            'high': -1.0,          # -1.5 to -1.0 = high
            'medium': -0.5,        # -1.0 to -0.5 = medium
            'low': 0.0             # -0.5 to 0.0 = low
        }
    
    def load_anomalies(self, filepath):
        """Load anomalies from detection report"""
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            self.anomalies = data.get('anomalies', [])
            logger.info(f"Loaded {len(self.anomalies)} anomalies")
            return True
        except Exception as e:
            logger.error(f"Error loading anomalies: {e}")
            return False
    
    def classify_severity(self, anomaly_score, rule_level):
        """Classify alert severity based on anomaly score and rule level"""
        # Combine anomaly score with rule level for severity
        combined_score = anomaly_score + (rule_level / 10)
        
        if combined_score < self.severity_thresholds['critical']:
            return AlertSeverity.CRITICAL
        elif combined_score < self.severity_thresholds['high']:
            return AlertSeverity.HIGH
        elif combined_score < self.severity_thresholds['medium']:
            return AlertSeverity.MEDIUM
        else:
            return AlertSeverity.LOW
    
    def process_anomalies(self):
        """Convert anomalies to alerts with severity classification"""
        alerts = []
        
        for anomaly in self.anomalies:
            severity = self.classify_severity(
                anomaly.get('anomaly_score', 0),
                anomaly.get('rule_level', 0)
            )
            
            alert = {
                'timestamp': datetime.now().isoformat(),
                'source': 'AI-Anomaly-Detector',
                'rule_id': anomaly.get('rule_id'),
                'rule_level': anomaly.get('rule_level'),
                'anomaly_score': anomaly.get('anomaly_score'),
                'severity': severity.name,
                'severity_level': severity.value,
                'description': anomaly.get('description'),
                'original_alert': anomaly.get('alert_timestamp'),
                'full_log': anomaly.get('full_log'),
                'recommended_action': self.get_recommended_action(severity, anomaly)
            }
            
            alerts.append(alert)
        
        self.alerts = sorted(alerts, key=lambda x: x['severity_level'], reverse=True)
        logger.info(f"Processed {len(alerts)} alerts")
        return alerts
    
    def get_recommended_action(self, severity, anomaly):
        """Get recommended incident response action"""
        actions = {
            AlertSeverity.CRITICAL: [
                "IMMEDIATE INVESTIGATION REQUIRED",
                "Block source IP if network-based attack",
                "Preserve evidence and logs",
                "Escalate to security team immediately",
                "Enable enhanced monitoring on affected system"
            ],
            AlertSeverity.HIGH: [
                "Investigate within 1 hour",
                "Review alert context and related events",
                "Prepare system for potential response",
                "Alert security operations center"
            ],
            AlertSeverity.MEDIUM: [
                "Schedule investigation within business hours",
                "Monitor for related alerts",
                "Document in incident management system"
            ],
            AlertSeverity.LOW: [
                "Log for trend analysis",
                "Review during routine security review",
                "Correlate with other low-severity alerts"
            ]
        }
        
        return actions.get(severity, ["Monitor and document"])
    
    def save_alerts(self, output_file='processed_alerts.json'):
        """Save processed alerts to JSON file"""
        output = {
            'timestamp': datetime.now().isoformat(),
            'total_alerts': len(self.alerts),
            'critical_count': sum(1 for a in self.alerts if a['severity'] == 'CRITICAL'),
            'high_count': sum(1 for a in self.alerts if a['severity'] == 'HIGH'),
            'medium_count': sum(1 for a in self.alerts if a['severity'] == 'MEDIUM'),
            'low_count': sum(1 for a in self.alerts if a['severity'] == 'LOW'),
            'alerts': self.alerts
        }
        
        with open(output_file, 'w') as f:
            json.dump(output, f, indent=2)
        
        logger.info(f"Alerts saved to {output_file}")
        return output
    
    def print_summary(self):
        """Print alert summary to console"""
        print("\n" + "="*70)
        print("WAZUH AI ALERT SUMMARY")
        print("="*70)
        print(f"Total Alerts: {len(self.alerts)}")
        print(f"Critical:     {sum(1 for a in self.alerts if a['severity'] == 'CRITICAL')}")
        print(f"High:         {sum(1 for a in self.alerts if a['severity'] == 'HIGH')}")
        print(f"Medium:       {sum(1 for a in self.alerts if a['severity'] == 'MEDIUM')}")
        print(f"Low:          {sum(1 for a in self.alerts if a['severity'] == 'LOW')}")
        print("="*70)
        
        print("\nCRITICAL ALERTS:")
        print("-"*70)
        critical_alerts = [a for a in self.alerts if a['severity'] == 'CRITICAL']
        if critical_alerts:
            for alert in critical_alerts[:5]:
                print(f"\n• Rule ID {alert['rule_id']}: {alert['description']}")
                print(f"  Anomaly Score: {alert['anomaly_score']:.4f}")
                print(f"  Recommended Actions:")
                for action in alert['recommended_action']:
                    print(f"    - {action}")
        else:
            print("No critical alerts")
        
        print("\n" + "="*70 + "\n")


def main():
    """Main execution"""
    if len(sys.argv) < 2:
        print("Usage: python3 alert_manager.py <anomalies_report_file>")
        print("Example: python3 alert_manager.py anomaly_report.json")
        sys.exit(1)
    
    report_file = sys.argv[1]
    
    manager = WazuhAlertManager()
    
    if not manager.load_anomalies(report_file):
        sys.exit(1)
    
    manager.process_anomalies()
    manager.save_alerts()
    manager.print_summary()


if __name__ == "__main__":
    main()
