This project is practice system design of an URL shortener.

Requirements:
- Simple UI to add a full URL and get back a shortened url
- Use minimal number of character for the use case (a bit non-sensical, but good for testing hashing and collision handling)
- Fast
- Handle possible collisions
- Redirect shortened url to full URL
- Track usage
- Unpredictable url (like an external tool)

Use case:
The url shortener would be an internal tool and host less than 
100k urls. 