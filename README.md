# Royal Grok AI Chat 👑

A elegant and sophisticated chat interface powered by X.AI's Grok model, featuring a royal theme and medieval English responses.

## Features

### Core Functionality
- Real-time chat interface with X.AI's Grok model
- Royal-themed responses in medieval English
- Markdown formatting support
- Password-protected access

### User Interface
- Elegant royal design theme
- Light/Dark mode toggle
- Responsive layout for all devices
- Smooth animations and transitions
- Message copy functionality
- Timestamp for each message

### Technical Features
- Rate limiting (50 requests per hour)
- Session management
- Error handling with themed messages
- Secure authentication
- Markdown parsing for formatted responses

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd royalAi
```

2. Install the required dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables in a `.env` file:
```env
XAI_API_KEY=your_xai_api_key
ADMIN_PASSWORD=your_admin_password
SECRET_KEY=your_secret_key
```

## Usage

1. Start the Flask server:
```bash
python main.py
```

2. Access the application at `http://localhost:5000`

3. Log in using the admin password

4. Start chatting with the Royal AI!

## Environment Variables

- `XAI_API_KEY`: Your X.AI API key
- `ADMIN_PASSWORD`: Password for accessing the chat interface
- `SECRET_KEY`: Secret key for Flask session management

## Dependencies

- Flask==3.0.0
- openai==1.57.0
- python-dotenv==1.0.0
- Flask-Limiter==3.5.0
- Additional dependencies listed in `requirements.txt`

## Features in Detail

### Authentication
- Secure login system
- Session management with 7-day persistence
- Protected routes

### Chat Interface
- Real-time message display
- Markdown formatting for responses
- Copy message functionality
- Timestamp display
- Smooth scrolling
- Loading animations

### Theme Support
- Light/Dark mode toggle
- Theme persistence across sessions
- Royal color scheme
- Responsive design for all screen sizes

## Deployment

The project is configured for deployment on Vercel:

1. Install Vercel CLI:
```bash
npm install -g vercel
```

2. Deploy to Vercel:
```bash
vercel
```

3. Set up environment variables in Vercel dashboard

## Error Handling

- Rate limit notifications
- API error handling
- Network error handling
- Session expiration handling
- Themed error messages

## Browser Support

- Chrome (recommended)
- Firefox
- Safari
- Edge
- Mobile browsers

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- X.AI for the Grok model API
- Showdown.js for Markdown parsing
- Flask framework
- Vercel for hosting

## Support

For support, please open an issue in the repository or contact the maintainers. 