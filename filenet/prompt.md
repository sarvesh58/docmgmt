Design a website similar to IBM FileNet focused on file storage, utilizing AWS S3 for storage solutions and Amazon DocumentDB for database management. The website should provide functionalities including user authentication, file upload/download, document management, and version control. Ensure that it follows best practices for security, scalability, and user experience.

### Requirements:
- **User Authentication:** Integrate user registration and login capabilities.
- **File Management:** Allow users to upload, download, and manage files, including file versioning and metadata.
- **Storage Solution:** Utilize AWS S3 for reliable file storage with options for lifecycle policies.
- **Database Management:** Use Amazon DocumentDB for efficient document storage and retrieval.
- **User Interface:** Create a user-friendly interface that is responsive and intuitive.
- **Security Features:** Implement encryption for files in transit and at rest, along with proper access controls.

### Steps:
1. *** AWS Account:** assume s3 resource name and docdb resource name.
2. **Develop Frontend:** Design the user interface using HTML, CSS, and JavaScript.
3. **Implement Backend:** Set up a server (Node.js, Python, or similar) that handles authentication, file processing, and database interactions.
4. **Connect to AWS Services:** Write code to interface with S3 and DocumentDB, ensuring error handling and performance optimization.
5. **Testing:** Create unit tests and perform user acceptance testing to ensure all features work as expected.
6. **Deployment:** Deploy the application using AWS services (e.g., Elastic Beanstalk, EC2).

### Output:
1. *** Project structure:** create the project structure in python .
2. use python to create the interface . 
3. for any interfaction with the s3 and the docdb create api's and let the web application use the api's to interact with the s3 resouces . 
4. have api's with below operations :
    Search operation: return only metadata of the file 
    retrieve operation: retrive file 
    retrieve file and metadata: retrive file with metadata 
    modify file and metadata : updata file and metadata
