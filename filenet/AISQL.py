import json
import boto3
import oracledb
import os
from typing import Dict, Any, List, Optional

# Initialize AWS clients
bedrock_runtime = boto3.client('bedrock-runtime', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
secrets_client = boto3.client('secretsmanager', region_name=os.environ.get('AWS_REGION', 'us-east-1'))

def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """
    Main Lambda handler for natural language to SQL queries
    """
    try:
        # Parse the incoming request
        body = json.loads(event.get('body', '{}')) if isinstance(event.get('body'), str) else event.get('body', {})
        user_query = body.get('query', '')
        
        if not user_query:
            return create_response(400, {'error': 'Query parameter is required'})
        
        # Get database schema for context
        schema_info = get_database_schema()
        
        # Convert natural language to SQL using Bedrock
        sql_query = convert_to_sql(user_query, schema_info)
        
        if not sql_query:
            return create_response(500, {'error': 'Failed to generate SQL query'})
        
        # Execute the SQL query
        query_results = execute_sql_query(sql_query)
        
        # Return the response
        return create_response(200, {
            'original_query': user_query,
            'generated_sql': sql_query,
            'results': query_results
        })
        
    except Exception as e:
        return create_response(500, {'error': f'Internal server error: {str(e)}'})

def get_database_credentials() -> Dict[str, str]:
    """
    Retrieve database credentials from AWS Secrets Manager
    """
    secret_name = os.environ.get('DB_SECRET_NAME', 'rds-credentials')
    
    try:
        response = secrets_client.get_secret_value(SecretId=secret_name)
        secret = json.loads(response['SecretString'])
        
        return {
            'host': secret.get('host', os.environ.get('DB_HOST')),
            'port': int(secret.get('port', os.environ.get('DB_PORT', 1521))),
            'username': secret.get('username', os.environ.get('DB_USERNAME')),
            'password': secret.get('password', os.environ.get('DB_PASSWORD')),
            'service_name': secret.get('service_name', os.environ.get('DB_SERVICE_NAME')),
            'sid': secret.get('sid', os.environ.get('DB_SID'))
        }
    except Exception as e:
        print(f"Error retrieving credentials: {str(e)}")
        # Fallback to environment variables
        return {
            'host': os.environ.get('DB_HOST'),
            'port': int(os.environ.get('DB_PORT', 1521)),
            'username': os.environ.get('DB_USERNAME'),
            'password': os.environ.get('DB_PASSWORD'),
            'service_name': os.environ.get('DB_SERVICE_NAME'),
            'sid': os.environ.get('DB_SID')
        }

def get_database_connection():
    """
    Create and return an Oracle database connection using oracledb
    """
    credentials = get_database_credentials()
    
    try:
        # Initialize oracledb in thin mode (no Oracle client required)
        oracledb.init_oracle_client()  # Optional: only needed for thick mode
    except Exception:
        # Thin mode doesn't require Oracle client - this is fine
        pass
    
    # Create connection parameters
    connection_params = {
        'user': credentials['username'],
        'password': credentials['password'],
        'host': credentials['host'],
        'port': credentials['port']
    }
    
    # Add service name or SID
    if credentials.get('service_name'):
        connection_params['service_name'] = credentials['service_name']
    elif credentials.get('sid'):
        connection_params['sid'] = credentials['sid']
    else:
        # Default service name for RDS
        connection_params['service_name'] = 'ORCL'
    
    # Additional connection options for better performance
    connection_params.update({
        'encoding': 'UTF-8',
        'nencoding': 'UTF-8',
        'events': True,  # Enable event handling
        'threaded': True,  # Enable threading support
        'pool': False  # Disable connection pooling for Lambda
    })
    
    return oracledb.connect(**connection_params)

def get_database_schema() -> str:
    """
    Retrieve Oracle database schema information to provide context for SQL generation
    """
    try:
        connection = get_database_connection()
        cursor = connection.cursor()
        
        # Get current user/schema
        cursor.execute("SELECT USER FROM DUAL")
        current_user = cursor.fetchone()[0]
        
        # Get all tables for the current user
        cursor.execute("""
            SELECT table_name 
            FROM user_tables 
            ORDER BY table_name
        """)
        tables = cursor.fetchall()
        
        schema_info = f"Oracle Database Schema (User: {current_user}):\n"
        
        for table_row in tables:
            table_name = table_row[0]
            schema_info += f"\nTable: {table_name}\n"
            
            # Get column information
            cursor.execute("""
                SELECT 
                    column_name,
                    data_type,
                    data_length,
                    data_precision,
                    data_scale,
                    nullable,
                    column_id
                FROM user_tab_columns 
                WHERE table_name = :table_name
                ORDER BY column_id
            """, {'table_name': table_name})
            
            columns = cursor.fetchall()
            
            # Get primary key information
            cursor.execute("""
                SELECT column_name
                FROM user_cons_columns ucc
                JOIN user_constraints uc ON ucc.constraint_name = uc.constraint_name
                WHERE uc.table_name = :table_name 
                AND uc.constraint_type = 'P'
            """, {'table_name': table_name})
            
            pk_columns = [row[0] for row in cursor.fetchall()]
            
            for column in columns:
                col_name = column[0]
                data_type = column[1]
                data_length = column[2]
                data_precision = column[3]
                data_scale = column[4]
                nullable = column[5]
                
                # Format data type with length/precision
                if data_type in ('VARCHAR2', 'CHAR', 'NVARCHAR2', 'NCHAR'):
                    type_info = f"{data_type}({data_length})"
                elif data_type == 'NUMBER' and data_precision:
                    if data_scale and data_scale > 0:
                        type_info = f"{data_type}({data_precision},{data_scale})"
                    else:
                        type_info = f"{data_type}({data_precision})"
                else:
                    type_info = data_type
                
                null_info = "NOT NULL" if nullable == 'N' else "NULL"
                pk_info = "PRIMARY KEY" if col_name in pk_columns else ""
                
                schema_info += f"  - {col_name} ({type_info}) {null_info} {pk_info}\n"
        
        cursor.close()
        connection.close()
        return schema_info
        
    except Exception as e:
        print(f"Error getting Oracle schema: {str(e)}")
        return "Oracle database schema unavailable"

def convert_to_sql(natural_language_query: str, schema_info: str) -> Optional[str]:
    """
    Use Amazon Bedrock to convert natural language to SQL
    """
    try:
        # Construct the prompt for the AI model
        prompt = f"""
You are an expert Oracle SQL developer. Given the following Oracle database schema and a natural language query, 
generate a precise Oracle SQL SELECT statement. Only return the SQL query, no explanations.

{schema_info}

Natural Language Query: {natural_language_query}

Rules:
1. Only generate SELECT statements (no INSERT, UPDATE, DELETE, DROP, etc.)
2. Use proper Oracle SQL syntax
3. Be conservative - if the query is ambiguous, ask for clarification
4. Use Oracle-specific functions when appropriate (e.g., SYSDATE, NVL, DECODE)
5. Use proper Oracle date formats and functions
6. Include appropriate WHERE clauses, JOINs, and ROWNUM for limiting results
7. Use Oracle table and column naming conventions (typically UPPERCASE)
8. Return only the SQL query without any markdown formatting or explanations

Oracle SQL Query:"""

        # Configure the model request
        model_id = os.environ.get('BEDROCK_MODEL_ID', 'anthropic.claude-3-sonnet-20240229-v1:0')
        
        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1000,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        }
        
        # Call Bedrock
        response = bedrock_runtime.invoke_model(
            modelId=model_id,
            body=json.dumps(request_body)
        )
        
        # Parse the response
        response_body = json.loads(response['body'].read())
        sql_query = response_body['content'][0]['text'].strip()
        
        # Clean up the SQL query (remove any markdown formatting)
        sql_query = sql_query.replace('```sql', '').replace('```', '').strip()
        
        # Basic validation - ensure it's a SELECT statement
        if not sql_query.upper().startswith('SELECT'):
            print(f"Generated query is not a SELECT statement: {sql_query}")
            return None
            
        return sql_query
        
    except Exception as e:
        print(f"Error converting to SQL: {str(e)}")
        return None

def execute_sql_query(sql_query: str) -> Dict[str, Any]:
    """
    Execute the generated SQL query against the Oracle RDS database using oracledb
    """
    try:
        connection = get_database_connection()
        cursor = connection.cursor()
        
        # Execute the query
        cursor.execute(sql_query)
        results = cursor.fetchall()
        
        # Get column names from cursor description
        column_names = [desc[0] for desc in cursor.description] if cursor.description else []
        
        # Convert Oracle data types to JSON-serializable types
        serialized_results = []
        for row in results:
            serialized_row = {}
            for i, value in enumerate(row):
                col_name = column_names[i]
                # Handle Oracle-specific data types with oracledb
                if hasattr(value, 'read'):  # Handle CLOB/BLOB
                    serialized_row[col_name] = value.read() if value else None
                elif isinstance(value, (oracledb.LOB,)):  # Handle LOB objects
                    serialized_row[col_name] = value.read() if value else None
                elif hasattr(value, 'isoformat'):  # Handle datetime objects
                    serialized_row[col_name] = value.isoformat()
                else:
                    serialized_row[col_name] = value
            serialized_results.append(serialized_row)
        
        cursor.close()
        connection.close()
        
        return {
            'success': True,
            'row_count': len(serialized_results),
            'columns': column_names,
            'data': serialized_results
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'row_count': 0,
            'columns': [],
            'data': []
        }

def create_response(status_code: int, body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a properly formatted Lambda response
    """
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'POST, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type, Authorization'
        },
        'body': json.dumps(body, default=str)  # default=str handles datetime serialization
    }

# Example usage and testing
if __name__ == "__main__":
    # Test event structure
    test_event = {
        'body': json.dumps({
            'query': 'Show me all employees who joined in the last 30 days'
        })
    }
    
    # Mock context
    class MockContext:
        function_name = 'test-function'
        memory_limit_in_mb = 128
        invoked_function_arn = 'arn:aws:lambda:us-east-1:123456789012:function:test'
        aws_request_id = 'test-request-id'
    
    result = lambda_handler(test_event, MockContext())
    print(json.dumps(result, indent=2))