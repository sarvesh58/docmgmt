import json
import boto3
from datetime import datetime, timedelta
import logging
from typing import Dict, List, Any
from botocore.exceptions import ClientError

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
cloudwatch = boto3.client('cloudwatch')
bedrock = boto3.client('bedrock-runtime')

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for CloudWatch Dashboard Widget with Bedrock Analysis
    
    This function can be called in two ways:
    1. As a CloudWatch custom widget (returns HTML/JSON for display)
    2. As a regular Lambda for analysis (returns analysis results)
    """
    
    try:
        # Determine if this is a CloudWatch widget request
        is_widget_request = event.get('describe', False) or event.get('widgetContext', {}).get('dashboard', {}).get('name')
        
        if is_widget_request:
            return handle_widget_request(event)
        else:
            return handle_analysis_request(event)
            
    except Exception as e:
        logger.error(f"Error in lambda_handler: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e)
            })
        }

def handle_widget_request(event: Dict[str, Any]) -> Dict[str, Any]:
    """Handle CloudWatch custom widget requests"""
    
    # If it's a describe request, return widget configuration
    if event.get('describe'):
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json'
            },
            'body': json.dumps({
                'name': 'Bedrock Dashboard Analyzer',
                'description': 'Analyzes CloudWatch dashboard metrics using AWS Bedrock',
                'parameters': {
                    'metrics': {
                        'type': 'array',
                        'description': 'List of CloudWatch metrics to analyze',
                        'default': []
                    },
                    'timeRange': {
                        'type': 'string',
                        'description': 'Time range for analysis (e.g., "1h", "24h", "7d")',
                        'default': '1h'
                    },
                    'analysisType': {
                        'type': 'string',
                        'description': 'Type of analysis to perform',
                        'default': 'summary'
                    }
                }
            })
        }
    
    # Handle widget display request
    try:
        # Get widget configuration
        widget_config = event.get('widgetContext', {})
        params = widget_config.get('params', {})
        
        # Get metrics data
        metrics_data = get_cloudwatch_metrics(params)
        
        # Analyze with Bedrock
        analysis = analyze_with_bedrock(metrics_data, params)
        
        # Generate HTML response for widget
        html_content = generate_widget_html(analysis, metrics_data)
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'text/html'
            },
            'body': html_content
        }
        
    except Exception as e:
        logger.error(f"Error handling widget request: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'text/html'
            },
            'body': f'<div style="color: red;">Error: {str(e)}</div>'
        }

def handle_analysis_request(event: Dict[str, Any]) -> Dict[str, Any]:
    """Handle direct analysis requests"""
    
    try:
        # Get metrics data
        metrics_data = get_cloudwatch_metrics(event)
        
        # Analyze with Bedrock
        analysis = analyze_with_bedrock(metrics_data, event)
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'analysis': analysis,
                'metricsData': metrics_data,
                'timestamp': datetime.utcnow().isoformat()
            })
        }
        
    except Exception as e:
        logger.error(f"Error handling analysis request: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e)
            })
        }

def get_cloudwatch_metrics(params: Dict[str, Any]) -> Dict[str, Any]:
    """Fetch CloudWatch metrics data"""
    
    # Parse time range
    time_range = params.get('timeRange', '1h')
    end_time = datetime.utcnow()
    
    if time_range == '1h':
        start_time = end_time - timedelta(hours=1)
        period = 300  # 5 minutes
    elif time_range == '24h':
        start_time = end_time - timedelta(days=1)
        period = 3600  # 1 hour
    elif time_range == '7d':
        start_time = end_time - timedelta(days=7)
        period = 86400  # 1 day
    else:
        start_time = end_time - timedelta(hours=1)
        period = 300
    
    # Default metrics if none specified
    default_metrics = [
        {
            'MetricName': 'CPUUtilization',
            'Namespace': 'AWS/EC2',
            'Dimensions': []
        },
        {
            'MetricName': 'Duration',
            'Namespace': 'AWS/Lambda',
            'Dimensions': []
        }
    ]
    
    metrics_config = params.get('metrics', default_metrics)
    metrics_data = {}
    
    for metric_config in metrics_config:
        try:
            metric_name = metric_config['MetricName']
            namespace = metric_config['Namespace']
            dimensions = metric_config.get('Dimensions', [])
            
            response = cloudwatch.get_metric_statistics(
                Namespace=namespace,
                MetricName=metric_name,
                Dimensions=dimensions,
                StartTime=start_time,
                EndTime=end_time,
                Period=period,
                Statistics=['Average', 'Maximum', 'Minimum']
            )
            
            metrics_data[f"{namespace}/{metric_name}"] = {
                'datapoints': response['Datapoints'],
                'label': response['Label'],
                'namespace': namespace,
                'metric_name': metric_name
            }
            
        except ClientError as e:
            logger.warning(f"Could not fetch metric {metric_config}: {str(e)}")
            continue
    
    return metrics_data

def analyze_with_bedrock(metrics_data: Dict[str, Any], params: Dict[str, Any]) -> str:
    """Analyze metrics data using AWS Bedrock"""
    
    # Prepare prompt for Bedrock
    analysis_type = params.get('analysisType', 'summary')
    
    # Create a summary of the metrics data
    metrics_summary = []
    for metric_key, metric_info in metrics_data.items():
        datapoints = metric_info['datapoints']
        if datapoints:
            values = [dp['Average'] for dp in datapoints if 'Average' in dp]
            if values:
                avg_value = sum(values) / len(values)
                max_value = max(values)
                min_value = min(values)
                
                metrics_summary.append({
                    'metric': metric_key,
                    'average': avg_value,
                    'maximum': max_value,
                    'minimum': min_value,
                    'datapoint_count': len(values)
                })
    
    # Create prompt based on analysis type
    if analysis_type == 'summary':
        prompt = f"""
        Please analyze the following CloudWatch metrics data and provide a comprehensive summary:

        Metrics Data:
        {json.dumps(metrics_summary, indent=2)}

        Please provide:
        1. Overall health assessment
        2. Notable trends or patterns
        3. Potential issues or concerns
        4. Recommendations for optimization

        Keep the response concise but informative.
        """
    elif analysis_type == 'anomaly':
        prompt = f"""
        Please analyze the following CloudWatch metrics data for anomalies:

        Metrics Data:
        {json.dumps(metrics_summary, indent=2)}

        Please identify:
        1. Any unusual patterns or spikes
        2. Metrics that are outside normal ranges
        3. Potential root causes
        4. Recommended actions

        Focus on anomaly detection and alerting.
        """
    else:
        prompt = f"""
        Please analyze the following CloudWatch metrics data:

        Metrics Data:
        {json.dumps(metrics_summary, indent=2)}

        Provide insights and recommendations based on the data.
        """
    
    # Call Bedrock API
    try:
        # Using Claude 3 Sonnet model - adjust model ID as needed
        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1000,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        }
        
        response = bedrock.invoke_model(
            body=json.dumps(body),
            modelId='anthropic.claude-3-sonnet-20240229-v1:0',
            accept='application/json',
            contentType='application/json'
        )
        
        response_body = json.loads(response.get('body').read())
        analysis = response_body.get('content', [{}])[0].get('text', 'No analysis available')
        
        return analysis
        
    except Exception as e:
        logger.error(f"Error calling Bedrock: {str(e)}")
        return f"Error performing analysis: {str(e)}"

def generate_widget_html(analysis: str, metrics_data: Dict[str, Any]) -> str:
    """Generate HTML content for CloudWatch widget display"""
    
    # Create a simple HTML widget
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{
                font-family: Arial, sans-serif;
                margin: 10px;
                background-color: #f5f5f5;
            }}
            .container {{
                background-color: white;
                border-radius: 8px;
                padding: 15px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }}
            .header {{
                color: #232f3e;
                font-size: 18px;
                font-weight: bold;
                margin-bottom: 15px;
                border-bottom: 2px solid #ff9900;
                padding-bottom: 5px;
            }}
            .analysis {{
                background-color: #f8f9fa;
                border-left: 4px solid #007dbc;
                padding: 10px;
                margin: 10px 0;
                border-radius: 4px;
            }}
            .metrics-summary {{
                margin-top: 15px;
                font-size: 12px;
                color: #666;
            }}
            .metric-item {{
                margin: 5px 0;
                padding: 5px;
                background-color: #f0f0f0;
                border-radius: 3px;
            }}
            .timestamp {{
                font-size: 10px;
                color: #999;
                text-align: right;
                margin-top: 10px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">🤖 Bedrock Dashboard Analysis</div>
            
            <div class="analysis">
                {analysis.replace(chr(10), '<br>')}
            </div>
            
            <div class="metrics-summary">
                <strong>Analyzed Metrics:</strong><br>
                {generate_metrics_summary_html(metrics_data)}
            </div>
            
            <div class="timestamp">
                Last updated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC
            </div>
        </div>
    </body>
    </html>
    """
    
    return html

def generate_metrics_summary_html(metrics_data: Dict[str, Any]) -> str:
    """Generate HTML summary of metrics data"""
    
    if not metrics_data:
        return '<div class="metric-item">No metrics data available</div>'
    
    html_parts = []
    for metric_key, metric_info in metrics_data.items():
        datapoints = metric_info['datapoints']
        if datapoints:
            values = [dp['Average'] for dp in datapoints if 'Average' in dp]
            if values:
                avg_value = sum(values) / len(values)
                html_parts.append(f'''
                <div class="metric-item">
                    <strong>{metric_key}</strong>: Avg {avg_value:.2f} 
                    ({len(values)} datapoints)
                </div>
                ''')
    
    return ''.join(html_parts) if html_parts else '<div class="metric-item">No data available</div>'

# Example configuration for CloudWatch Dashboard Widget
WIDGET_CONFIG_EXAMPLE = {
    "type": "custom",
    "width": 12,
    "height": 6,
    "properties": {
        "endpoint": "arn:aws:lambda:us-east-1:123456789012:function:cloudwatch-bedrock-analyzer",
        "title": "Bedrock Dashboard Analysis",
        "params": {
            "metrics": [
                {
                    "MetricName": "CPUUtilization",
                    "Namespace": "AWS/EC2",
                    "Dimensions": []
                }
            ],
            "timeRange": "1h",
            "analysisType": "summary"
        }
    }
}
