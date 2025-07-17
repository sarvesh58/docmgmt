import json
import boto3
from datetime import datetime, timedelta
import logging
from typing import Dict, List, Any, Optional
from botocore.exceptions import ClientError
from concurrent.futures import ThreadPoolExecutor, as_completed

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
cloudwatch = boto3.client('cloudwatch')
bedrock = boto3.client('bedrock-runtime')
lambda_client = boto3.client('lambda')
stepfunctions = boto3.client('stepfunctions')
sqs = boto3.client('sqs')
logs_client = boto3.client('logs')

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for analyzing specific AWS resources:
    - 5 Lambda functions
    - 1 Step Function
    - 2 SQS queues
    - 2 SQS DLQ queues
    """
    
    try:
        # Check if this is a widget request
        is_widget_request = event.get('describe', False) or event.get('widgetContext', {}).get('dashboard', {}).get('name')
        
        if is_widget_request:
            return handle_widget_request(event)
        else:
            return handle_focused_analysis(event)
            
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
    
    if event.get('describe'):
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json'
            },
            'body': json.dumps({
                'name': 'Focused AWS Resource Analyzer',
                'description': 'Analyzes Lambda, Step Functions, and SQS resources',
                'parameters': {
                    'lambdaFunctions': {
                        'type': 'array',
                        'description': 'List of Lambda function names to analyze',
                        'default': []
                    },
                    'stepFunctions': {
                        'type': 'array',
                        'description': 'List of Step Function ARNs to analyze',
                        'default': []
                    },
                    'sqsQueues': {
                        'type': 'array',
                        'description': 'List of SQS queue URLs to analyze',
                        'default': []
                    },
                    'sqsDlqQueues': {
                        'type': 'array',
                        'description': 'List of SQS DLQ queue URLs to analyze',
                        'default': []
                    },
                    'timeRange': {
                        'type': 'string',
                        'description': 'Time range for analysis (1h, 24h, 7d)',
                        'default': '1h'
                    }
                }
            })
        }
    
    # Handle widget display request
    try:
        widget_config = event.get('widgetContext', {})
        params = widget_config.get('params', {})
        
        # Get all metrics data
        all_metrics_data = get_all_resources_metrics(params)
        
        # Analyze with Bedrock
        analysis = analyze_with_bedrock(all_metrics_data, params)
        
        # Generate HTML response for widget
        html_content = generate_widget_html(analysis, all_metrics_data)
        
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

def handle_focused_analysis(event: Dict[str, Any]) -> Dict[str, Any]:
    """Handle direct analysis requests"""
    
    try:
        # Get all metrics data
        all_metrics_data = get_all_resources_metrics(event)
        
        # Analyze with Bedrock
        analysis = analyze_with_bedrock(all_metrics_data, event)
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'analysis': analysis,
                'resourcesAnalyzed': {
                    'lambdaFunctions': len(all_metrics_data.get('lambda', {})),
                    'stepFunctions': len(all_metrics_data.get('stepfunctions', {})),
                    'sqsQueues': len(all_metrics_data.get('sqs', {})),
                    'sqsDlqQueues': len(all_metrics_data.get('sqs_dlq', {}))
                },
                'metricsData': all_metrics_data,
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

def get_all_resources_metrics(params: Dict[str, Any]) -> Dict[str, Any]:
    """Get metrics for all specified resources"""
    
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
    
    all_metrics = {}
    
    # Get Lambda function metrics
    lambda_functions = params.get('lambdaFunctions', [])
    if not lambda_functions:
        # Auto-discover Lambda functions if not specified
        lambda_functions = discover_lambda_functions()[:5]  # Limit to 5 as requested
    
    if lambda_functions:
        all_metrics['lambda'] = get_lambda_metrics(lambda_functions, start_time, end_time, period)
        # Get Lambda logs and errors
        all_metrics['lambda_logs'] = get_lambda_logs_analysis(lambda_functions, start_time, end_time)
    
    # Get Step Function metrics
    step_functions = params.get('stepFunctions', [])
    if not step_functions:
        # Auto-discover Step Functions if not specified
        step_functions = discover_step_functions()[:1]  # Limit to 1 as requested
    
    if step_functions:
        all_metrics['stepfunctions'] = get_stepfunction_metrics(step_functions, start_time, end_time, period)
        # Get Step Function execution logs
        all_metrics['stepfunctions_logs'] = get_stepfunction_logs_analysis(step_functions, start_time, end_time)
    
    # Get SQS queue metrics
    sqs_queues = params.get('sqsQueues', [])
    if not sqs_queues:
        # Auto-discover SQS queues if not specified
        discovered_queues = discover_sqs_queues()
        sqs_queues = [q for q in discovered_queues if not q.endswith('-dlq')][:2]  # Non-DLQ queues
    
    if sqs_queues:
        all_metrics['sqs'] = get_sqs_metrics(sqs_queues, start_time, end_time, period)
    
    # Get SQS DLQ metrics
    sqs_dlq_queues = params.get('sqsDlqQueues', [])
    if not sqs_dlq_queues:
        # Auto-discover SQS DLQ queues if not specified
        discovered_queues = discover_sqs_queues()
        sqs_dlq_queues = [q for q in discovered_queues if q.endswith('-dlq') or 'dlq' in q.lower()][:2]  # DLQ queues
    
    if sqs_dlq_queues:
        all_metrics['sqs_dlq'] = get_sqs_metrics(sqs_dlq_queues, start_time, end_time, period, is_dlq=True)
    
    return all_metrics

def discover_lambda_functions() -> List[str]:
    """Discover Lambda functions in the account"""
    try:
        response = lambda_client.list_functions()
        return [func['FunctionName'] for func in response['Functions']]
    except ClientError as e:
        logger.error(f"Error discovering Lambda functions: {str(e)}")
        return []

def discover_step_functions() -> List[str]:
    """Discover Step Functions in the account"""
    try:
        response = stepfunctions.list_state_machines()
        return [sm['stateMachineArn'] for sm in response['stateMachines']]
    except ClientError as e:
        logger.error(f"Error discovering Step Functions: {str(e)}")
        return []

def discover_sqs_queues() -> List[str]:
    """Discover SQS queues in the account"""
    try:
        response = sqs.list_queues()
        return response.get('QueueUrls', [])
    except ClientError as e:
        logger.error(f"Error discovering SQS queues: {str(e)}")
        return []

def get_lambda_metrics(function_names: List[str], start_time: datetime, end_time: datetime, period: int) -> Dict[str, Any]:
    """Get metrics for Lambda functions"""
    
    lambda_metrics = ['Duration', 'Errors', 'Throttles', 'Invocations', 'ConcurrentExecutions']
    results = {}
    
    for function_name in function_names:
        results[function_name] = {}
        
        for metric_name in lambda_metrics:
            try:
                response = cloudwatch.get_metric_statistics(
                    Namespace='AWS/Lambda',
                    MetricName=metric_name,
                    Dimensions=[
                        {
                            'Name': 'FunctionName',
                            'Value': function_name
                        }
                    ],
                    StartTime=start_time,
                    EndTime=end_time,
                    Period=period,
                    Statistics=['Average', 'Sum', 'Maximum']
                )
                
                results[function_name][metric_name] = {
                    'datapoints': response['Datapoints'],
                    'label': response['Label']
                }
                
            except ClientError as e:
                logger.warning(f"Could not fetch Lambda metric {metric_name} for {function_name}: {str(e)}")
                continue
    
    return results

def get_lambda_logs_analysis(function_names: List[str], start_time: datetime, end_time: datetime) -> Dict[str, Any]:
    """Analyze Lambda function logs for errors and patterns"""
    
    logs_analysis = {}
    
    for function_name in function_names:
        log_group_name = f"/aws/lambda/{function_name}"
        
        try:
            # Get log streams for the function
            log_streams_response = logs_client.describe_log_streams(
                logGroupName=log_group_name,
                orderBy='LastEventTime',
                descending=True,
                limit=10  # Get recent log streams
            )
            
            log_streams = log_streams_response.get('logStreams', [])
            
            if not log_streams:
                logs_analysis[function_name] = {
                    'error': 'No log streams found',
                    'error_patterns': [],
                    'recent_errors': [],
                    'log_stats': {}
                }
                continue
            
            # Analyze logs from recent streams
            function_errors = []
            error_patterns = {}
            total_log_events = 0
            
            for log_stream in log_streams[:5]:  # Check last 5 streams
                stream_name = log_stream['logStreamName']
                
                try:
                    # Get log events
                    log_events_response = logs_client.get_log_events(
                        logGroupName=log_group_name,
                        logStreamName=stream_name,
                        startTime=int(start_time.timestamp() * 1000),
                        endTime=int(end_time.timestamp() * 1000),
                        limit=100  # Limit to avoid too much data
                    )
                    
                    events = log_events_response.get('events', [])
                    total_log_events += len(events)
                    
                    for event in events:
                        message = event.get('message', '')
                        timestamp = event.get('timestamp', 0)
                        
                        # Check for error patterns
                        if any(error_keyword in message.lower() for error_keyword in 
                               ['error', 'exception', 'failed', 'timeout', 'traceback']):
                            
                            # Extract error type
                            error_type = extract_error_type(message)
                            
                            if error_type in error_patterns:
                                error_patterns[error_type] += 1
                            else:
                                error_patterns[error_type] = 1
                            
                            # Store recent errors (last 10)
                            if len(function_errors) < 10:
                                function_errors.append({
                                    'timestamp': datetime.fromtimestamp(timestamp / 1000).isoformat(),
                                    'message': message.strip()[:200],  # Truncate long messages
                                    'error_type': error_type,
                                    'stream': stream_name
                                })
                
                except ClientError as e:
                    logger.warning(f"Could not get log events for {stream_name}: {str(e)}")
                    continue
            
            # Calculate log statistics
            log_stats = {
                'total_log_events': total_log_events,
                'error_count': len(function_errors),
                'unique_error_types': len(error_patterns),
                'error_rate': (len(function_errors) / total_log_events * 100) if total_log_events > 0 else 0
            }
            
            logs_analysis[function_name] = {
                'error_patterns': error_patterns,
                'recent_errors': function_errors,
                'log_stats': log_stats
            }
            
        except ClientError as e:
            logger.warning(f"Could not analyze logs for {function_name}: {str(e)}")
            logs_analysis[function_name] = {
                'error': f"Could not access logs: {str(e)}",
                'error_patterns': {},
                'recent_errors': [],
                'log_stats': {}
            }
    
    return logs_analysis

def extract_error_type(message: str) -> str:
    """Extract error type from log message"""
    
    # Common error patterns
    error_patterns = [
        r'(\w+Error)',
        r'(\w+Exception)',
        r'(TimeoutError|Timeout)',
        r'(MemoryError|OutOfMemoryError)',
        r'(ConnectionError|ConnectTimeout)',
        r'(KeyError|AttributeError|ValueError|TypeError)',
        r'(ImportError|ModuleNotFoundError)',
        r'(PermissionError|AccessDenied)',
        r'(NetworkError|HTTPError)',
        r'(DatabaseError|SQLError)'
    ]
    
    import re
    
    for pattern in error_patterns:
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            return match.group(1)
    
    # If no specific pattern found, look for general error indicators
    if 'timeout' in message.lower():
        return 'TimeoutError'
    elif 'memory' in message.lower():
        return 'MemoryError'
    elif 'connection' in message.lower():
        return 'ConnectionError'
    elif 'permission' in message.lower() or 'access' in message.lower():
        return 'PermissionError'
    elif 'not found' in message.lower():
        return 'NotFoundError'
    else:
        return 'GeneralError'

def get_stepfunction_logs_analysis(state_machine_arns: List[str], start_time: datetime, end_time: datetime) -> Dict[str, Any]:
    """Analyze Step Function execution logs for errors"""
    
    logs_analysis = {}
    
    for arn in state_machine_arns:
        sm_name = arn.split(':')[-1]
        
        try:
            # Get recent executions
            response = stepfunctions.list_executions(
                stateMachineArn=arn,
                statusFilter='FAILED',
                maxResults=10
            )
            
            failed_executions = response.get('executions', [])
            
            # Get execution details for failed executions
            execution_errors = []
            error_patterns = {}
            
            for execution in failed_executions:
                execution_arn = execution['executionArn']
                
                try:
                    # Get execution history
                    history_response = stepfunctions.get_execution_history(
                        executionArn=execution_arn,
                        maxResults=50,
                        reverseOrder=True
                    )
                    
                    events = history_response.get('events', [])
                    
                    for event in events:
                        event_type = event.get('type', '')
                        
                        # Look for failure events
                        if 'Failed' in event_type or 'Aborted' in event_type:
                            event_details = event.get('executionFailedEventDetails', {}) or \
                                          event.get('executionAbortedEventDetails', {}) or \
                                          event.get('taskFailedEventDetails', {})
                            
                            if event_details:
                                error_message = event_details.get('error', 'Unknown error')
                                cause = event_details.get('cause', '')
                                
                                error_type = extract_error_type(error_message)
                                
                                if error_type in error_patterns:
                                    error_patterns[error_type] += 1
                                else:
                                    error_patterns[error_type] = 1
                                
                                execution_errors.append({
                                    'execution_arn': execution_arn,
                                    'timestamp': event.get('timestamp', '').isoformat() if event.get('timestamp') else '',
                                    'error_type': error_type,
                                    'error_message': error_message,
                                    'cause': cause[:200] if cause else ''
                                })
                
                except ClientError as e:
                    logger.warning(f"Could not get execution history for {execution_arn}: {str(e)}")
                    continue
            
            logs_analysis[sm_name] = {
                'failed_executions_count': len(failed_executions),
                'error_patterns': error_patterns,
                'recent_errors': execution_errors[:10],  # Last 10 errors
                'execution_stats': {
                    'total_failed_executions': len(failed_executions),
                    'unique_error_types': len(error_patterns)
                }
            }
            
        except ClientError as e:
            logger.warning(f"Could not analyze Step Function logs for {sm_name}: {str(e)}")
            logs_analysis[sm_name] = {
                'error': f"Could not access execution logs: {str(e)}",
                'error_patterns': {},
                'recent_errors': [],
                'execution_stats': {}
            }
    
    return logs_analysis

def get_stepfunction_metrics(state_machine_arns: List[str], start_time: datetime, end_time: datetime, period: int) -> Dict[str, Any]:
    """Get metrics for Step Functions"""
    
    sf_metrics = ['ExecutionsFailed', 'ExecutionsSucceeded', 'ExecutionTime', 'ExecutionsAborted']
    results = {}
    
    for arn in state_machine_arns:
        # Extract state machine name from ARN
        sm_name = arn.split(':')[-1]
        results[sm_name] = {}
        
        for metric_name in sf_metrics:
            try:
                response = cloudwatch.get_metric_statistics(
                    Namespace='AWS/States',
                    MetricName=metric_name,
                    Dimensions=[
                        {
                            'Name': 'StateMachineArn',
                            'Value': arn
                        }
                    ],
                    StartTime=start_time,
                    EndTime=end_time,
                    Period=period,
                    Statistics=['Average', 'Sum', 'Maximum']
                )
                
                results[sm_name][metric_name] = {
                    'datapoints': response['Datapoints'],
                    'label': response['Label']
                }
                
            except ClientError as e:
                logger.warning(f"Could not fetch Step Function metric {metric_name} for {sm_name}: {str(e)}")
                continue
    
    return results

def get_sqs_metrics(queue_urls: List[str], start_time: datetime, end_time: datetime, period: int, is_dlq: bool = False) -> Dict[str, Any]:
    """Get metrics for SQS queues"""
    
    sqs_metrics = ['ApproximateNumberOfMessages', 'ApproximateNumberOfMessagesVisible', 
                   'NumberOfMessagesSent', 'NumberOfMessagesReceived', 'NumberOfMessagesDeleted']
    results = {}
    
    for queue_url in queue_urls:
        # Extract queue name from URL
        queue_name = queue_url.split('/')[-1]
        results[queue_name] = {}
        
        for metric_name in sqs_metrics:
            try:
                response = cloudwatch.get_metric_statistics(
                    Namespace='AWS/SQS',
                    MetricName=metric_name,
                    Dimensions=[
                        {
                            'Name': 'QueueName',
                            'Value': queue_name
                        }
                    ],
                    StartTime=start_time,
                    EndTime=end_time,
                    Period=period,
                    Statistics=['Average', 'Sum', 'Maximum']
                )
                
                results[queue_name][metric_name] = {
                    'datapoints': response['Datapoints'],
                    'label': response['Label'],
                    'is_dlq': is_dlq
                }
                
            except ClientError as e:
                logger.warning(f"Could not fetch SQS metric {metric_name} for {queue_name}: {str(e)}")
                continue
    
    return results

def analyze_with_bedrock(all_metrics_data: Dict[str, Any], params: Dict[str, Any]) -> str:
    """Analyze all metrics data using AWS Bedrock"""
    
    # Create comprehensive summary including logs
    analysis_summary = {
        'lambda_functions': {},
        'lambda_logs': {},
        'step_functions': {},
        'stepfunctions_logs': {},
        'sqs_queues': {},
        'sqs_dlq_queues': {}
    }
    
    # Process Lambda metrics
    for func_name, metrics in all_metrics_data.get('lambda', {}).items():
        func_summary = {}
        for metric_name, metric_data in metrics.items():
            datapoints = metric_data.get('datapoints', [])
            if datapoints:
                if metric_name == 'Duration':
                    values = [dp.get('Average', 0) for dp in datapoints]
                elif metric_name in ['Errors', 'Throttles', 'Invocations']:
                    values = [dp.get('Sum', 0) for dp in datapoints]
                else:
                    values = [dp.get('Average', 0) for dp in datapoints]
                
                if values:
                    func_summary[metric_name] = {
                        'average': sum(values) / len(values),
                        'maximum': max(values),
                        'total': sum(values) if metric_name in ['Errors', 'Throttles', 'Invocations'] else None
                    }
        
        analysis_summary['lambda_functions'][func_name] = func_summary
    
    # Process Lambda logs
    for func_name, log_data in all_metrics_data.get('lambda_logs', {}).items():
        analysis_summary['lambda_logs'][func_name] = log_data
    
    # Process Step Function metrics
    for sf_name, metrics in all_metrics_data.get('stepfunctions', {}).items():
        sf_summary = {}
        for metric_name, metric_data in metrics.items():
            datapoints = metric_data.get('datapoints', [])
            if datapoints:
                values = [dp.get('Sum', 0) for dp in datapoints]
                if values:
                    sf_summary[metric_name] = {
                        'total': sum(values),
                        'average': sum(values) / len(values)
                    }
        
        analysis_summary['step_functions'][sf_name] = sf_summary
    
    # Process Step Function logs
    for sf_name, log_data in all_metrics_data.get('stepfunctions_logs', {}).items():
        analysis_summary['stepfunctions_logs'][sf_name] = log_data
    
    # Process SQS metrics
    for queue_name, metrics in all_metrics_data.get('sqs', {}).items():
        queue_summary = {}
        for metric_name, metric_data in metrics.items():
            datapoints = metric_data.get('datapoints', [])
            if datapoints:
                values = [dp.get('Average', 0) for dp in datapoints]
                if values:
                    queue_summary[metric_name] = {
                        'average': sum(values) / len(values),
                        'maximum': max(values)
                    }
        
        analysis_summary['sqs_queues'][queue_name] = queue_summary
    
    # Process SQS DLQ metrics
    for queue_name, metrics in all_metrics_data.get('sqs_dlq', {}).items():
        queue_summary = {}
        for metric_name, metric_data in metrics.items():
            datapoints = metric_data.get('datapoints', [])
            if datapoints:
                values = [dp.get('Average', 0) for dp in datapoints]
                if values:
                    queue_summary[metric_name] = {
                        'average': sum(values) / len(values),
                        'maximum': max(values)
                    }
        
        analysis_summary['sqs_dlq_queues'][queue_name] = queue_summary
    
    # Create detailed prompt for Bedrock
    prompt = f"""
    Please analyze the following AWS serverless infrastructure metrics AND logs data to provide comprehensive insights:

    LAMBDA FUNCTIONS METRICS:
    {json.dumps(analysis_summary['lambda_functions'], indent=2)}

    LAMBDA FUNCTIONS LOGS & ERRORS:
    {json.dumps(analysis_summary['lambda_logs'], indent=2)}

    STEP FUNCTIONS METRICS:
    {json.dumps(analysis_summary['step_functions'], indent=2)}

    STEP FUNCTIONS EXECUTION LOGS & ERRORS:
    {json.dumps(analysis_summary['stepfunctions_logs'], indent=2)}

    SQS QUEUES ANALYSIS:
    {json.dumps(analysis_summary['sqs_queues'], indent=2)}

    SQS DEAD LETTER QUEUES ANALYSIS:
    {json.dumps(analysis_summary['sqs_dlq_queues'], indent=2)}

    Please provide:
    1. **Overall System Health**: Assessment of the serverless architecture
    2. **Lambda Performance & Error Analysis**: 
       - Duration, invocation patterns, and error rates
       - Detailed error patterns and root causes from logs
       - Common exceptions and their frequency
    3. **Step Function Workflow Analysis**: 
       - Execution success/failure rates
       - Failed execution analysis with specific error causes
       - Workflow bottlenecks and failure points
    4. **Message Queue Health**: SQS message flow and processing efficiency
    5. **Critical Error Patterns**: 
       - Most frequent error types across all services
       - Error correlation between services
       - Potential cascading failures
    6. **Root Cause Analysis**: Deep dive into specific errors from logs
    7. **Performance Bottlenecks**: Identified issues from metrics and logs
    8. **Actionable Recommendations**: 
       - Specific fixes for identified errors
       - Performance optimization suggestions
       - Monitoring and alerting improvements
    9. **Immediate Actions**: Critical issues requiring urgent attention

    Focus on correlating metrics with actual log errors to provide actionable insights.
    """
    
    # Call Bedrock API
    try:
        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 2000,
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

def generate_widget_html(analysis: str, all_metrics_data: Dict[str, Any]) -> str:
    """Generate HTML content for CloudWatch widget display"""
    
    # Count resources
    lambda_count = len(all_metrics_data.get('lambda', {}))
    sf_count = len(all_metrics_data.get('stepfunctions', {}))
    sqs_count = len(all_metrics_data.get('sqs', {}))
    dlq_count = len(all_metrics_data.get('sqs_dlq', {}))
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                margin: 8px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                font-size: 12px;
            }}
            .container {{
                background: rgba(255, 255, 255, 0.1);
                backdrop-filter: blur(10px);
                border-radius: 12px;
                padding: 15px;
                box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
                border: 1px solid rgba(255, 255, 255, 0.2);
            }}
            .header {{
                font-size: 16px;
                font-weight: bold;
                margin-bottom: 15px;
                text-align: center;
                background: rgba(255, 255, 255, 0.1);
                padding: 10px;
                border-radius: 8px;
                border: 1px solid rgba(255, 255, 255, 0.2);
            }}
            .resource-summary {{
                display: grid;
                grid-template-columns: repeat(4, 1fr);
                gap: 10px;
                margin-bottom: 15px;
            }}
            .resource-card {{
                background: rgba(255, 255, 255, 0.1);
                padding: 8px;
                border-radius: 8px;
                text-align: center;
                border: 1px solid rgba(255, 255, 255, 0.2);
            }}
            .resource-count {{
                font-size: 18px;
                font-weight: bold;
                color: #ffd700;
            }}
            .resource-label {{
                font-size: 10px;
                margin-top: 2px;
            }}
            .analysis {{
                background: rgba(0, 0, 0, 0.2);
                border-radius: 8px;
                padding: 12px;
                margin: 10px 0;
                border-left: 4px solid #ffd700;
                max-height: 400px;
                overflow-y: auto;
                line-height: 1.4;
            }}
            .timestamp {{
                font-size: 9px;
                color: rgba(255, 255, 255, 0.7);
                text-align: right;
                margin-top: 10px;
            }}
            .analysis::-webkit-scrollbar {{
                width: 6px;
            }}
            .analysis::-webkit-scrollbar-track {{
                background: rgba(255, 255, 255, 0.1);
                border-radius: 3px;
            }}
            .analysis::-webkit-scrollbar-thumb {{
                background: rgba(255, 255, 255, 0.3);
                border-radius: 3px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                🚀 Serverless Architecture Analysis
            </div>
            
            <div class="resource-summary">
                <div class="resource-card">
                    <div class="resource-count">{lambda_count}</div>
                    <div class="resource-label">Lambda Functions</div>
                </div>
                <div class="resource-card">
                    <div class="resource-count">{sf_count}</div>
                    <div class="resource-label">Step Functions</div>
                </div>
                <div class="resource-card">
                    <div class="resource-count">{sqs_count}</div>
                    <div class="resource-label">SQS Queues</div>
                </div>
                <div class="resource-card">
                    <div class="resource-count">{dlq_count}</div>
                    <div class="resource-label">DLQ Queues</div>
                </div>
            </div>
            
            <div class="analysis">
                {analysis.replace(chr(10), '<br>')}
            </div>
            
            <div class="timestamp">
                Last updated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC
            </div>
        </div>
    </body>
    </html>
    """
    
    return html

# Example usage configuration
EXAMPLE_CONFIG = {
    "lambdaFunctions": [
        "user-service-handler",
        "order-processing-lambda",
        "payment-processor",
        "notification-service",
        "data-transformer"
    ],
    "stepFunctions": [
        "arn:aws:states:us-east-1:123456789012:stateMachine:OrderProcessingWorkflow"
    ],
    "sqsQueues": [
        "https://sqs.us-east-1.amazonaws.com/123456789012/order-queue",
        "https://sqs.us-east-1.amazonaws.com/123456789012/notification-queue"
    ],
    "sqsDlqQueues": [
        "https://sqs.us-east-1.amazonaws.com/123456789012/order-queue-dlq",
        "https://sqs.us-east-1.amazonaws.com/123456789012/notification-queue-dlq"
    ],
    "timeRange": "1h"
}
