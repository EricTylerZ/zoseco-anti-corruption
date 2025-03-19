## Installation Instructions

1. **Set up the server:**
   ```bash
   pip install flask flask-socketio flask-cors requests
   ```

2. **Set environment variables:**
   ```bash
   export LLM_API_URL="https://api.openai.com/v1/chat/completions"  # or Venice.ai URL
   export LLM_API_KEY="your-api-key-here"
   ```

3. **Start the server:**
   ```bash
   python app.py
   ```

4. **Add the widget to your website:**
   Add this script tag to the bottom of your zoseco.com pages:
   ```html
   <script src="https://your-server-url.com/widget.js"></script>
   ```

## Customization Options

1. **Widget appearance:** Modify the CSS in the widget.js file
2. **LLM integration:** Update the get_ai_response function in app.py
3. **For Venice.ai:** Change the API URL and request format to match Venice.ai's API
4. **Database storage:** Replace the in-memory storage with a database like SQLite, PostgreSQL, or MongoDB
5. **User authentication:** Add login for admin users to access the dashboard

Remember to replace placeholder values like "your-server-url.com" with your actual server address.

This gives you a complete chat system with both customer-facing widget and an admin dashboard, all with LLM integration and real-time messaging.