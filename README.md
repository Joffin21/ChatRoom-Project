# Chat Room

This project is a real-time, multi-room chat application. The backend is built with Python and FastAPI, using WebSockets for real-time communication and SQLAlchemy for database interaction. The entire application is containerized with Docker for easy and consistent deployment.

## Key Features & Completed Milestones

The application has been developed from a simple, single-room chat server into a more robust, stateful application.

### Core Functionality
-   **Multi-Room Chat**: Users can create and join different chat rooms.
-   **Real-time Communication**: Built with WebSockets to ensure that messages are broadcast instantly to all participants in a room.
-   **Dockerized Environment**: The application is fully containerized, ensuring a consistent environment for both development and deployment.

### Lobby & Room Management
-   **Central Lobby**: Upon connecting, users enter a central lobby where they can see lists of both active and existing chat rooms.
    -   **Active Rooms**: A list of rooms that currently have one or more users in them.
    -   **Existing Rooms**: A list of all rooms that have been created and not yet closed, even if they are currently empty.
-   **Seamless Navigation**: Users can join rooms from the lobby and use a "Leave Room" button to return to the lobby without needing to refresh the page.

### User & Admin Persistence
-   **Database Integration**: The application uses a SQLite database to store users, rooms, and message history. SQLAlchemy is used as the ORM.
-   **Persistent Message History**: All messages are saved to the database. When a user joins a room, they receive the full message history.
-   **Admin Controls**: The user who creates a room becomes its administrator.
    -   Admins have the ability to "close" a room, which kicks all participants and permanently deletes the room and its message history.
-   **Auto-Rejoin**: The application remembers a user's last-visited room. Upon returning, if the room is still open, the user is automatically placed back in it, bypassing the lobby for a smoother experience.

## How to Run the Application

The application is containerized with Docker for easy setup and execution.

1.  **Ensure Docker is running** on your machine.
2.  **Build the Docker image:**
    ```bash
    docker build -t chatroom-app .
    ```
3.  **Run the container:**
    ```bash
    docker run -d --name chatroom-container -p 8000:8000 chatroom-app
    ```

Once the container is running, the application will be accessible at [http://localhost:8000](http://localhost:8000).

## Future Goals & Potential Milestones

While the current application is functional, there are many opportunities for future development to create a more feature-rich and production-ready system.

### Immediate Next Steps
-   **Enhanced UI/UX**:
    -   Improve the visual design and layout for a more polished and intuitive user experience.
    -   Add real-time feedback, such as "User is typing..." indicators.
-   **More Robust Error Handling**: Implement more specific error handling on both the frontend and backend to gracefully manage unexpected issues.

### Advanced Features
-   **Private Messaging**: Allow users to send direct, one-to-one messages to each other outside of public chat rooms.
-   **User Authentication**: Implement a proper authentication system (e.g., OAuth2) to allow users to register accounts and log in securely, replacing the current simple username entry.
-   **Scalability**:
    -   Migrate from SQLite to a more robust database like PostgreSQL.
    -   Implement a message broker like Redis Pub/Sub to handle message broadcasting across multiple instances of the application, enabling horizontal scaling.
-   **Testing**: Develop a comprehensive test suite, including unit tests for the backend logic and end-to-end tests for the user flows.
-   **Deployment**: Create a production-ready deployment pipeline using tools like Docker Compose and a reverse proxy (e.g., Nginx).

## What I've Learned

This project served as a practical exercise in several key backend technologies and concepts.

### Application Architecture
-   **FastAPI vs. Uvicorn**: FastAPI is the web framework that defines our application's logic and endpoints. Uvicorn is the high-performance ASGI server that actually runs the application, listening for and responding to network requests. While alternatives like Hypercorn exist, Uvicorn is the standard for FastAPI. For production, a process manager like Gunicorn is often used to manage Uvicorn workers for greater stability.
-   **Separation of Concerns**: We structured our code to be maintainable.
    -   `main.py`: Handles web requests and WebSocket connection logic.
    -   `models.py`: Defines the database schema using SQLAlchemy's ORM. This is the single source of truth for our data structure.
    -   `crud.py`: Contains all database interaction functions (Create, Read, Update, Delete). This isolates our business logic from our database logic, making the code cleaner and easier to test.

### Database Choices
-   **Relational (SQL) vs. NoSQL**: We chose a relational database (SQLite) because our application's data is highly relational (users have messages, messages belong to rooms, rooms have admins). This model is ideal for enforcing data integrity and querying relationships between different types of data. A NoSQL database might be better suited for unstructured data or massive horizontal scaling.
-   **SQLAlchemy ORM**: The Object-Relational Mapper allows us to interact with our database using Python classes and objects instead of writing raw SQL. This improves readability, reduces errors, and helps prevent vulnerabilities like SQL injection.

### Python Concepts
-   **Type Hinting**: Using the `typing` library (e.g., `Dict`, `List`) doesn't change how the code runs, but it vastly improves code quality by making it more readable, enabling static analysis tools to catch bugs early, and serving as a form of inline documentation.

### DevOps and Deployment
-   **The "Why" of Docker**: Docker was created to solve the "it works on my machine" problem. It eliminates inconsistencies between development, staging, and production environments by packaging the application, its dependencies, and the necessary parts of its operating system into a standard, portable unit called a container.
-   **Image vs. Container**: A Docker **image** is a static blueprint or template. A **container** is a live, running instance of an image.
-   **Port Mapping**: The `-p 8000:8000` flag is the crucial bridge that connects a port on the host machine to a port inside the isolated container, allowing external traffic (like from our browser) to reach the application running inside.
