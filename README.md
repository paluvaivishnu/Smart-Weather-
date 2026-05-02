# Smart Weather App

A beautiful, modern desktop weather application built with Python and PyQt5. 
The app fetches a 5-day forecast from the OpenWeather API and provides smart outfit and activity recommendations based on the weather conditions.

## Features
- **5-Day Forecast:** Get detailed weather predictions for any city.
- **Smart Recommendations:** Outfit suggestions and activity viability based on temperature and weather conditions.
- **Beautiful UI:** A clean, modern interface with smooth gradients, shadows, and weather-themed accents.
- **City Autocomplete:** Start typing to get suggestions for popular cities.

## Requirements
- Python 3.7+
- PyQt5
- python-dotenv
- requests
- geonamescache (optional, for enhanced city autocomplete)

## Setup and Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/paluvaivishnu/Smart-Weather-.git
   cd Smart-Weather-
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **API Key Setup:**
   - Create an account on [OpenWeatherMap](https://openweathermap.org/) and get a free API key.
   - Create a `.env` file in the root directory.
   - Add your API key to the `.env` file:
     ```env
     OPENWEATHER_API_KEY=your_api_key_here
     ```

## Usage

Run the application:
```bash
python app.py
```
Or use the runner script:
```bash
python run.py
```

- Enter a city name in the input box.
- (Optional) Enter an activity you're planning (e.g., "hiking", "cricket").
- Click **Get Forecast** to see the 5-day weather projection and recommendations.

## License
MIT License
