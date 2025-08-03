import xml.etree.ElementTree as ET
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union
import logging
import os
import zipfile
import json

logger = logging.getLogger(__name__)

class AppleHealthConnector:
    """
    Connector for Apple Health data exported from iPhone Health app
    Processes the export.xml file for diabetes-related data
    """
    
    def __init__(self, export_file_path: str = None):
        self.export_file_path = export_file_path
        self.health_data = None
        self.processed_data = None
        
        # Apple Health data types - focused on key diabetes monitoring metrics
        self.diabetes_data_types = {
            'HKQuantityTypeIdentifierBloodGlucose': 'blood_glucose',
            'HKQuantityTypeIdentifierHeartRate': 'heart_rate',
            'HKCategoryTypeIdentifierSleepAnalysis': 'sleep',
            'HKWorkoutTypeIdentifier': 'workout'
        }
    
    def load_apple_health_export(self, file_path: str = None) -> bool:
        """
        Load Apple Health export file (XML or ZIP)
        
        Args:
            file_path: Path to export.xml or Health Data.zip file
        """
        if file_path:
            self.export_file_path = file_path
            
        if not self.export_file_path or not os.path.exists(self.export_file_path):
            logger.error(f"Export file not found: {self.export_file_path}")
            return False
        
        try:
            # Handle ZIP file (standard Apple Health export)
            if self.export_file_path.endswith('.zip'):
                with zipfile.ZipFile(self.export_file_path, 'r') as zip_file:
                    # Look for export.xml in the zip
                    xml_files = [f for f in zip_file.namelist() if f.endswith('export.xml')]
                    if not xml_files:
                        logger.error("No export.xml found in ZIP file")
                        return False
                    
                    with zip_file.open(xml_files[0]) as xml_file:
                        self.health_data = ET.parse(xml_file)
            else:
                # Direct XML file
                self.health_data = ET.parse(self.export_file_path)
            
            logger.info("Successfully loaded Apple Health export")
            return True
            
        except Exception as e:
            logger.error(f"Error loading Apple Health export: {e}")
            return False
    
    def extract_diabetes_data(self, days_back: int = 90) -> pd.DataFrame:
        """
        Extract diabetes-related data from Apple Health export
        
        Args:
            days_back: Number of days back to extract data
        """
        if not self.health_data:
            logger.error("No health data loaded. Call load_apple_health_export() first.")
            return pd.DataFrame()
        
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        records = []
        root = self.health_data.getroot()
        
        # Process Record elements
        for record in root.findall('.//Record'):
            try:
                record_type = record.get('type')
                
                # Skip if not diabetes-related
                if record_type not in self.diabetes_data_types:
                    continue
                
                # Parse timestamp
                start_time_str = record.get('startDate')
                end_time_str = record.get('endDate')
                
                if not start_time_str:
                    continue
                
                # Parse Apple Health timestamp format
                start_time = self._parse_apple_timestamp(start_time_str)
                end_time = self._parse_apple_timestamp(end_time_str) if end_time_str else start_time
                
                # Filter by date range
                if start_time < start_date or start_time > end_date:
                    continue
                
                # Extract basic record info
                base_record = {
                    'timestamp': start_time,
                    'end_timestamp': end_time,
                    'data_type': self.diabetes_data_types[record_type],
                    'apple_health_type': record_type,
                    'source_name': record.get('sourceName', ''),
                    'source_version': record.get('sourceVersion', ''),
                    'device': record.get('device', ''),
                    'creation_date': self._parse_apple_timestamp(record.get('creationDate', start_time_str)),
                    'source': 'apple_health'
                }
                
                # Extract value and unit
                value_str = record.get('value')
                unit = record.get('unit', '')
                
                if value_str:
                    try:
                        value = float(value_str)
                        base_record.update({
                            'value': value,
                            'unit': unit,
                            'original_value': value_str
                        })
                    except ValueError:
                        base_record.update({
                            'value': None,
                            'unit': unit,
                            'original_value': value_str
                        })
                
                # Process specific data types
                if record_type == 'HKQuantityTypeIdentifierBloodGlucose':
                    glucose_mg_dl = self._convert_glucose_to_mg_dl(value, unit)
                    base_record.update({
                        'glucose_mg_dl': glucose_mg_dl,
                        'glucose_mmol_l': glucose_mg_dl * 0.0555 if glucose_mg_dl else None,
                        'measurement_type': 'fingerstick'  # Assume fingerstick unless specified
                    })
                
                elif record_type == 'HKQuantityTypeIdentifierHeartRate':
                    base_record.update({
                        'heart_rate_bpm': value,
                        'heart_rate_unit': unit
                    })
                
                elif record_type == 'HKCategoryTypeIdentifierSleepAnalysis':
                    # Sleep data is handled differently - it's a category, not quantity
                    sleep_value = record.get('value', '')
                    base_record.update({
                        'sleep_stage': sleep_value,
                        'sleep_duration_hours': (end_time - start_time).total_seconds() / 3600
                    })
                
                # Extract metadata if present
                metadata = {}
                for meta_entry in record.findall('.//MetadataEntry'):
                    key = meta_entry.get('key', '')
                    meta_value = meta_entry.get('value', '')
                    metadata[key] = meta_value
                
                if metadata:
                    base_record['metadata'] = metadata
                    
                    # Check for CGM data indicators
                    if 'HKWasUserEntered' in metadata:
                        was_user_entered = metadata['HKWasUserEntered'].lower() == 'true'
                        if record_type == 'HKQuantityTypeIdentifierBloodGlucose' and not was_user_entered:
                            base_record['measurement_type'] = 'cgm'
                
                records.append(base_record)
                
            except Exception as e:
                logger.warning(f"Error processing Apple Health record: {e}")
                continue
        
        # Process Sleep data (handled separately as it's a category type)
        for sleep_record in root.findall('.//Record[@type="HKCategoryTypeIdentifierSleepAnalysis"]'):
            try:
                start_time_str = sleep_record.get('startDate')
                end_time_str = sleep_record.get('endDate')
                
                if not start_time_str or not end_time_str:
                    continue
                
                start_time = self._parse_apple_timestamp(start_time_str)
                end_time = self._parse_apple_timestamp(end_time_str)
                
                if start_time < start_date or start_time > end_date:
                    continue
                
                sleep_value = sleep_record.get('value', 'HKCategoryValueSleepAnalysisInBed')
                
                sleep_record_data = {
                    'timestamp': start_time,
                    'end_timestamp': end_time,
                    'data_type': 'sleep',
                    'apple_health_type': 'HKCategoryTypeIdentifierSleepAnalysis',
                    'sleep_stage': sleep_value,
                    'sleep_duration_hours': (end_time - start_time).total_seconds() / 3600,
                    'source_name': sleep_record.get('sourceName', ''),
                    'source_version': sleep_record.get('sourceVersion', ''),
                    'device': sleep_record.get('device', ''),
                    'creation_date': self._parse_apple_timestamp(sleep_record.get('creationDate', start_time_str)),
                    'source': 'apple_health'
                }
                
                records.append(sleep_record_data)
                
            except Exception as e:
                logger.warning(f"Error processing sleep record: {e}")
                continue
        for workout in root.findall('.//Workout'):
            try:
                start_time_str = workout.get('startDate')
                if not start_time_str:
                    continue
                
                start_time = self._parse_apple_timestamp(start_time_str)
                end_time = self._parse_apple_timestamp(workout.get('endDate', start_time_str))
                
                if start_time < start_date or start_time > end_date:
                    continue
                
                workout_record = {
                    'timestamp': start_time,
                    'end_timestamp': end_time,
                    'data_type': 'workout',
                    'workout_type': workout.get('workoutActivityType', ''),
                    'duration_minutes': (end_time - start_time).total_seconds() / 60,
                    'total_distance': float(workout.get('totalDistance', 0)),
                    'total_energy_burned': float(workout.get('totalEnergyBurned', 0)),
                    'source_name': workout.get('sourceName', ''),
                    'source': 'apple_health'
                }
                
                records.append(workout_record)
                
            except Exception as e:
                logger.warning(f"Error processing workout record: {e}")
                continue
        
        if not records:
            logger.warning("No diabetes-related records found in Apple Health export")
            return pd.DataFrame()
        
        df = pd.DataFrame(records)
        df = df.sort_values('timestamp').reset_index(drop=True)
        
        # Add derived fields
        df['hour'] = df['timestamp'].dt.hour
        df['day_of_week'] = df['timestamp'].dt.day_name()
        df['date'] = df['timestamp'].dt.date
        
        logger.info(f"Extracted {len(df)} Apple Health records (glucose, heart rate, sleep, exercise)")
        return df
    
    def _parse_apple_timestamp(self, timestamp_str: str) -> datetime:
        """Parse Apple Health timestamp format"""
        try:
            # Apple Health uses format like "2025-01-15 14:30:25 -0800"
            # Remove timezone for simplicity
            clean_timestamp = timestamp_str.split(' -')[0].split(' +')[0]
            return datetime.strptime(clean_timestamp, "%Y-%m-%d %H:%M:%S")
        except Exception as e:
            logger.warning(f"Error parsing timestamp {timestamp_str}: {e}")
            return datetime.now()
    
    def _convert_glucose_to_mg_dl(self, value: float, unit: str) -> Optional[float]:
        """Convert glucose values to mg/dL"""
        if not value:
            return None
        
        if unit == 'mg/dL':
            return value
        elif unit == 'mmol/L':
            return value * 18.0182  # Convert mmol/L to mg/dL
        else:
            logger.warning(f"Unknown glucose unit: {unit}")
            return value
    
    def get_cgm_data(self, days_back: int = 30) -> pd.DataFrame:
        """
        Extract specifically CGM data from Apple Health
        
        Args:
            days_back: Number of days back to extract
        """
        all_data = self.extract_diabetes_data(days_back)
        
        if all_data.empty:
            return pd.DataFrame()
        
        # Filter for glucose data that's likely from CGM
        cgm_data = all_data[
            (all_data['data_type'] == 'blood_glucose') &
            (all_data['measurement_type'] == 'cgm')
        ].copy()
        
        if cgm_data.empty:
            # Fallback: look for frequent glucose readings (likely CGM)
            glucose_data = all_data[all_data['data_type'] == 'blood_glucose'].copy()
            if not glucose_data.empty:
                # Group by source and check frequency
                source_counts = glucose_data.groupby('source_name').size()
                high_frequency_sources = source_counts[source_counts > 100].index
                
                cgm_data = glucose_data[
                    glucose_data['source_name'].isin(high_frequency_sources)
                ].copy()
        
        return cgm_data
    
    def get_heart_rate_summary(self, days_back: int = 7) -> Dict:
        """Get heart rate summary and patterns from Apple Health"""
        all_data = self.extract_diabetes_data(days_back)
        
        if all_data.empty:
            return {}
        
        heart_rate_data = all_data[all_data['data_type'] == 'heart_rate']
        
        if heart_rate_data.empty:
            return {"message": "No heart rate data found in Apple Health"}
        
        # Calculate heart rate statistics
        hr_values = heart_rate_data['heart_rate_bpm'].dropna()
        
        if len(hr_values) == 0:
            return {"message": "No valid heart rate readings found"}
        
        # Analyze patterns
        daily_hr = heart_rate_data.groupby('date')['heart_rate_bpm'].agg([
            'mean', 'min', 'max', 'count'
        ]).round(1)
        
        hourly_hr = heart_rate_data.groupby('hour')['heart_rate_bpm'].mean().round(1)
        
        summary = {
            "analysis_period": f"Last {days_back} days",
            "total_readings": len(heart_rate_data),
            "average_heart_rate": round(hr_values.mean(), 1),
            "resting_heart_rate_estimate": round(hr_values.quantile(0.1), 1),  # Bottom 10% as proxy for resting
            "max_heart_rate": round(hr_values.max(), 1),
            "heart_rate_variability": round(hr_values.std(), 1),
            "daily_averages": {
                "mean_daily_hr": round(daily_hr['mean'].mean(), 1) if not daily_hr.empty else None,
                "readings_per_day": round(daily_hr['count'].mean(), 1) if not daily_hr.empty else None
            },
            "hourly_patterns": {
                f"{hour:02d}:00": float(hr_avg) 
                for hour, hr_avg in hourly_hr.items() 
                if not pd.isna(hr_avg)
            }
        }
        
        return summary
    
    def get_sleep_summary(self, days_back: int = 14) -> Dict:
        """Get sleep summary and patterns from Apple Health"""
        all_data = self.extract_diabetes_data(days_back)
        
        if all_data.empty:
            return {}
        
        sleep_data = all_data[all_data['data_type'] == 'sleep']
        
        if sleep_data.empty:
            return {"message": "No sleep data found in Apple Health"}
        
        # Group by date to get nightly sleep totals
        daily_sleep = sleep_data.groupby('date').agg({
            'sleep_duration_hours': 'sum',
            'sleep_stage': lambda x: list(x.unique())
        })
        
        # Calculate sleep statistics
        total_sleep_hours = daily_sleep['sleep_duration_hours']
        
        summary = {
            "analysis_period": f"Last {days_back} days",
            "nights_with_data": len(daily_sleep),
            "average_sleep_hours": round(total_sleep_hours.mean(), 1) if not total_sleep_hours.empty else None,
            "min_sleep_hours": round(total_sleep_hours.min(), 1) if not total_sleep_hours.empty else None,
            "max_sleep_hours": round(total_sleep_hours.max(), 1) if not total_sleep_hours.empty else None,
            "sleep_consistency": round(total_sleep_hours.std(), 1) if not total_sleep_hours.empty else None,
            "sleep_stages_detected": list(sleep_data['sleep_stage'].unique()),
            "weekly_pattern": {}
        }
        
        # Weekly sleep patterns
        sleep_data['day_of_week'] = sleep_data['timestamp'].dt.day_name()
        weekly_sleep = sleep_data.groupby('day_of_week')['sleep_duration_hours'].sum()
        summary["weekly_pattern"] = {day: round(hours, 1) for day, hours in weekly_sleep.items()}
        
        return summary
    
    def get_exercise_summary(self, days_back: int = 14) -> Dict:
        """Get exercise summary and patterns from Apple Health"""
        all_data = self.extract_diabetes_data(days_back)
        
        if all_data.empty:
            return {}
        
        exercise_data = all_data[all_data['data_type'] == 'workout']
        
        if exercise_data.empty:
            return {"message": "No exercise data found in Apple Health"}
        
        # Calculate exercise statistics
        total_workouts = len(exercise_data)
        total_duration = exercise_data['duration_minutes'].sum()
        total_calories = exercise_data['total_energy_burned'].sum()
        
        # Group by workout type
        workout_types = exercise_data.groupby('workout_type').agg({
            'duration_minutes': ['count', 'sum', 'mean'],
            'total_energy_burned': 'sum'
        }).round(1)
        
        # Weekly exercise pattern
        exercise_data['day_of_week'] = exercise_data['timestamp'].dt.day_name()
        weekly_exercise = exercise_data.groupby('day_of_week').agg({
            'duration_minutes': 'sum',
            'workout_type': 'count'
        })
        
        summary = {
            "analysis_period": f"Last {days_back} days",
            "total_workouts": total_workouts,
            "total_exercise_minutes": round(total_duration, 1),
            "total_calories_burned": round(total_calories, 1),
            "average_workout_duration": round(exercise_data['duration_minutes'].mean(), 1) if total_workouts > 0 else 0,
            "workouts_per_week": round((total_workouts / days_back) * 7, 1),
            "workout_types": {
                workout_type: {
                    "count": int(stats[('duration_minutes', 'count')]),
                    "total_minutes": float(stats[('duration_minutes', 'sum')]),
                    "avg_duration": float(stats[('duration_minutes', 'mean')]),
                    "total_calories": float(stats[('total_energy_burned', 'sum')])
                }
                for workout_type, stats in workout_types.iterrows()
            },
            "weekly_pattern": {
                day: {
                    "total_minutes": round(float(data['duration_minutes']), 1),
                    "workout_count": int(data['workout_type'])
                }
                for day, data in weekly_exercise.iterrows()
            }
        }
        
        return summary
    
    def export_processed_data(self, output_file: str = "apple_health_diabetes_data.json"):
        """Export processed data to JSON for integration with MCP server"""
        if self.processed_data is None:
            self.processed_data = self.extract_diabetes_data()
        
        if self.processed_data.empty:
            logger.warning("No data to export")
            return False
        
        # Convert DataFrame to JSON-serializable format
        export_data = {
            "export_date": datetime.now().isoformat(),
            "total_records": len(self.processed_data),
            "data_types": self.processed_data['data_type'].value_counts().to_dict(),
            "date_range": {
                "start": self.processed_data['timestamp'].min().isoformat(),
                "end": self.processed_data['timestamp'].max().isoformat()
            },
            "records": []
        }
        
        # Convert each record
        for _, row in self.processed_data.iterrows():
            record = {}
            for col, value in row.items():
                if pd.isna(value):
                    record[col] = None
                elif isinstance(value, (pd.Timestamp, datetime)):
                    record[col] = value.isoformat()
                elif isinstance(value, np.integer):
                    record[col] = int(value)
                elif isinstance(value, np.floating):
                    record[col] = float(value)
                else:
                    record[col] = value
            export_data["records"].append(record)
        
        try:
            with open(output_file, 'w') as f:
                json.dump(export_data, f, indent=2)
            logger.info(f"Apple Health data exported to {output_file}")
            return True
        except Exception as e:
            logger.error(f"Error exporting data: {e}")
            return False

# Integration functions for MCP server
def integrate_apple_health_data(patient_id: int, apple_health_file: str, days_back: int = 30) -> Dict:
    """
    Integrate Apple Health data with existing patient data system
    
    Args:
        patient_id: Patient identifier to associate with Apple Health data
        apple_health_file: Path to Apple Health export file
        days_back: Number of days of data to process
    """
    try:
        connector = AppleHealthConnector()
        
        if not connector.load_apple_health_export(apple_health_file):
            return {"error": "Failed to load Apple Health export file"}
        
        # Extract diabetes data
        apple_data = connector.extract_diabetes_data(days_back)
        
        if apple_data.empty:
            return {
                "patient_id": patient_id,
                "message": "No diabetes-related data found in Apple Health export",
                "processed_records": 0
            }
        
        # Get CGM data specifically
        cgm_data = connector.get_cgm_data(days_back)
        nutrition_summary = connector.get_nutrition_summary(7)
        
        # Analyze the data
        glucose_data = apple_data[apple_data['data_type'] == 'blood_glucose']
        insulin_data = apple_data[apple_data['data_type'] == 'insulin_delivery']
        
        summary = {
            "patient_id": patient_id,
            "apple_health_integration": {
                "total_records": len(apple_data),
                "data_types_found": apple_data['data_type'].value_counts().to_dict(),
                "date_range": {
                    "start": apple_data['timestamp'].min().isoformat(),
                    "end": apple_data['timestamp'].max().isoformat()
                },
                "sources": apple_data['source_name'].unique().tolist()
            },
            "glucose_data": {
                "total_readings": len(glucose_data),
                "cgm_readings": len(cgm_data),
                "fingerstick_readings": len(glucose_data[glucose_data['measurement_type'] == 'fingerstick']),
                "average_glucose": round(glucose_data['glucose_mg_dl'].mean(), 1) if not glucose_data.empty else None,
                "glucose_range": {
                    "min": round(glucose_data['glucose_mg_dl'].min(), 1) if not glucose_data.empty else None,
                    "max": round(glucose_data['glucose_mg_dl'].max(), 1) if not glucose_data.empty else None
                }
            },
            "insulin_data": {
                "total_entries": len(insulin_data),
                "total_units": round(insulin_data['insulin_units'].sum(), 1) if not insulin_data.empty else 0
            },
            "nutrition_summary": nutrition_summary
        }
        
        return summary
        
    except Exception as e:
        logger.error(f"Error integrating Apple Health data: {e}")
        return {"error": str(e), "patient_id": patient_id}

def get_apple_health_glucose_patterns(apple_health_file: str, days_back: int = 14) -> Dict:
    """
    Analyze glucose patterns specifically from Apple Health data
    """
    try:
        connector = AppleHealthConnector()
        
        if not connector.load_apple_health_export(apple_health_file):
            return {"error": "Failed to load Apple Health export file"}
        
        # Get CGM data for pattern analysis
        cgm_data = connector.get_cgm_data(days_back)
        
        if cgm_data.empty:
            return {"error": "No CGM data found in Apple Health export"}
        
        # Analyze hourly patterns
        hourly_stats = cgm_data.groupby('hour')['glucose_mg_dl'].agg([
            'mean', 'std', 'count', 'min', 'max'
        ]).round(1)
        
        # Time in range analysis
        glucose_values = cgm_data['glucose_mg_dl'].dropna()
        time_in_range = {
            "very_low_under_54": round((glucose_values < 54).mean() * 100, 1),
            "low_54_to_70": round(((glucose_values >= 54) & (glucose_values < 70)).mean() * 100, 1),
            "target_70_to_180": round(((glucose_values >= 70) & (glucose_values <= 180)).mean() * 100, 1),
            "high_180_to_250": round(((glucose_values > 180) & (glucose_values <= 250)).mean() * 100, 1),
            "very_high_over_250": round((glucose_values > 250).mean() * 100, 1)
        }
        
        return {
            "data_source": "Apple Health CGM",
            "analysis_period": f"Last {days_back} days",
            "total_cgm_readings": len(cgm_data),
            "average_glucose": round(glucose_values.mean(), 1),
            "glucose_variability": round(glucose_values.std(), 1),
            "time_in_ranges": {f"{k}": f"{v}%" for k, v in time_in_range.items()},
            "hourly_patterns": {
                f"{hour:02d}:00": {
                    "avg_glucose": float(stats['mean']),
                    "readings_count": int(stats['count'])
                }
                for hour, stats in hourly_stats.iterrows()
                if stats['count'] > 0
            }
        }
        
    except Exception as e:
        logger.error(f"Error analyzing Apple Health glucose patterns: {e}")
        return {"error": str(e)}

# Test function
def test_apple_health_integration():
    """Test Apple Health integration functionality"""
    print("=== Testing Apple Health Integration ===")
    
    # Test with sample file (you'll need to provide the actual file path)
    sample_file = "export.xml"  # or "Health Data.zip"
    
    if not os.path.exists(sample_file):
        print(f"❌ Sample file {sample_file} not found")
        print("To test Apple Health integration:")
        print("1. Export your health data from iPhone Health app")
        print("2. Share the Health Data.zip file")
        print("3. Update the sample_file path in this test")
        return
    
    connector = AppleHealthConnector()
    
    # Test loading
    print("1. Loading Apple Health export...")
    if connector.load_apple_health_export(sample_file):
        print("✅ Successfully loaded export file")
    else:
        print("❌ Failed to load export file")
        return
    
    # Test data extraction
    print("2. Extracting diabetes data...")
    diabetes_data = connector.extract_diabetes_data(30)
    print(f"✅ Extracted {len(diabetes_data)} records")
    
    if not diabetes_data.empty:
        print("Data types found:")
        for dtype, count in diabetes_data['data_type'].value_counts().items():
            print(f"  {dtype}: {count}")
    
    # Test CGM data
    print("3. Extracting CGM data...")
    cgm_data = connector.get_cgm_data(30)
    print(f"✅ Found {len(cgm_data)} CGM readings")
    
    # Test integration
    print("4. Testing integration function...")
    result = integrate_apple_health_data(12345, sample_file, 7)
    print("✅ Integration completed")
    print(f"Total records: {result.get('apple_health_integration', {}).get('total_records', 0)}")

if __name__ == "__main__":
    test_apple_health_integration()