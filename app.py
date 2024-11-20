
import os
import base64
import re
import pandas as pd
import matplotlib.pyplot as plt
import io
import seaborn as sns  # Import seaborn for heatmap

from flask import Flask, render_template

app = Flask(__name__)

# Folder to store decoded images
UPLOAD_FOLDER = 'static/images'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Safe regex search function
def safe_search(pattern, text):
    match = re.search(pattern, text)
    return match.group(1) if match else None

# Decode Base64 image and save it
def decode_base64_image(base64_string, filename):
    try:
        img_data = base64.b64decode(base64_string)
        with open(os.path.join(UPLOAD_FOLDER, filename), 'wb') as img_file:
            img_file.write(img_data)
        print(f"Image saved as {filename}")
    except Exception as e:
        print(f"Error saving image {filename}: {e}")

# Parse log file and return cleaned DataFrame
def parse_log_file():
    log_file_path = 'logs.txt' 
    try:
        with open(log_file_path, 'r') as file:
            log_content = file.read()
    except FileNotFoundError:
        print("Log file 'logs.txt' not found!")
        return pd.DataFrame()

    # Extract plain logs
    plain_data_pattern = r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}) (.*)'
    plain_data = re.findall(plain_data_pattern, log_content)

    df = pd.DataFrame(plain_data, columns=["timestamp", "log_message"])
    df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
    df = df.dropna(subset=["timestamp"])  # Remove invalid timestamps

    # Add derived fields
    df['hour'] = df['timestamp'].dt.hour
    df['weekday'] = df['timestamp'].dt.day_name()
    df['user'] = df['log_message'].apply(lambda x: x.split()[0] if len(x.split()) > 1 else 'unknown')
    df['log_message_length'] = df['log_message'].apply(len)
    df['action_type'] = df['log_message'].apply(lambda x: safe_search(r'action=([^ ]*)', x) or 'login')

    # Look for Base64 images in log messages and save them
    base64_pattern = r'img_data=([A-Za-z0-9+/=]+)'
    base64_images = re.findall(base64_pattern, log_content)
    for i, img_base64 in enumerate(base64_images):
        filename = f'image_{i}.png'
        print(f"Found Base64 image: {filename}")
        decode_base64_image(img_base64, filename)

    return df

def create_plot(plot_func, *args, **kwargs):
    figsize = kwargs.pop("figsize", (8, 5))
    title = kwargs.pop("title", None)
    xlabel = kwargs.pop("xlabel", None)
    ylabel = kwargs.pop("ylabel", None)

    plt.figure(figsize=figsize)
    plot_func(*args, **kwargs)

    if title:
        plt.title(title)
    if xlabel:
        plt.xlabel(xlabel)
    if ylabel:
        plt.ylabel(ylabel)

    plt.tight_layout()
    img = io.BytesIO()
    plt.savefig(img, format='png', bbox_inches="tight")
    img.seek(0)
    plt.close()
    return base64.b64encode(img.getvalue()).decode('utf8')

@app.route('/')
def dashboard():
    df = parse_log_file()
    plots = []

    # 1. Logs Over Time (Hourly)
    hourly_logs = df.set_index('timestamp').resample('H').size()
    plots.append(create_plot(hourly_logs.plot, title="Logs Over Time (Hourly)", color='blue', xlabel='Time', ylabel='Log Count'))

    # 2. Top 5 Events (Pie Chart)
    top_events = df['log_message'].value_counts().head(5)
    plots.append(create_plot(top_events.plot, kind='pie', autopct='%1.1f%%', startangle=90, title="Top 5 Log Events"))

    # 3. Log Activity Heatmap (Hourly Distribution)
    hourly_pivot = df.groupby('hour').size().reset_index(name='log_count').pivot_table(index='hour', values='log_count')
    plots.append(create_plot(sns.heatmap, hourly_pivot, annot=True, cmap='coolwarm'))
    plt.title("Log Activity by Hour")

    # 4. Top 10 Users by Log Count (Bar Chart)
    top_users = df['user'].value_counts().head(10)
    plots.append(create_plot(top_users.plot, kind='bar', title="Top 10 Users by Log Count", color='green', xlabel='Users', ylabel='Log Count', rot=45))

    # 5. Cumulative Log Trend (Line Plot)
    cumulative_logs = df.set_index('timestamp').resample('D').size().cumsum()
    plots.append(create_plot(cumulative_logs.plot, title="Cumulative Log Trend", color='purple', xlabel="Date", ylabel="Cumulative Log Count"))

    # 6. Log Distribution by Weekday (Bar Chart)
    weekday_counts = df['weekday'].value_counts()
    plots.append(create_plot(weekday_counts.plot, kind='bar', title="Log Distribution by Weekday", color='orange', xlabel='Weekday', ylabel='Log Count', rot=45))

    # 7. Average Log Message Length by Hour (Line Plot)
    avg_log_length = df.groupby('hour')['log_message_length'].mean()
    plots.append(create_plot(avg_log_length.plot, marker='o', title="Average Log Message Length by Hour", xlabel="Hour", ylabel="Avg Log Message Length"))

    # 8. Log Message Length vs Hour (Scatter Plot)
    plots.append(create_plot(plt.scatter, df['hour'], df['log_message_length'], alpha=0.5, title="Log Message Length vs Hour", xlabel='Hour of Day', ylabel='Log Message Length'))

    # 9. Action Type Distribution (Pie Chart)
    action_counts = df['action_type'].value_counts()
    plots.append(create_plot(action_counts.plot, kind='pie', autopct='%1.1f%%', startangle=90, title="Action Type Distribution"))

    # 10. Log Message Length Distribution (Histogram)
    plots.append(create_plot(plt.hist, df['log_message_length'], bins=20, color='skyblue', edgecolor='black', title="Log Message Length Distribution", xlabel="Message Length", ylabel="Frequency"))

    # Images for Display
    image_files = os.listdir(UPLOAD_FOLDER)
    image_files = [os.path.join(UPLOAD_FOLDER, f) for f in image_files if f.endswith('.png')]

    return render_template('dashboard.html', plot_images=plots, image_files=image_files)

if __name__ == '__main__':
    app.run(debug=True)
