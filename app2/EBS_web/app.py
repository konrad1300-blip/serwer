from flask import Flask, render_template, request

app = Flask(__name__)

# Szerokości liter w milimetrach (odwzorowanie z kodu Pascal)
LETTER_WIDTHS = {
    # małe litery
    'a': 35, 'b': 34, 'c': 33, 'd': 35, 'e': 33, 'f': 22.5, 'g': 34.5,
    'h': 33, 'i': 15, 'j': 19, 'k': 33, 'l': 15, 'm': 51, 'n': 34,
    'o': 37.5, 'p': 34, 'q': 36, 'r': 23.5, 's': 34.5, 't': 23,
    'u': 34, 'v': 33.5, 'w': 48.5, 'x': 35, 'y': 34, 'z': 31.5,
    # wielkie litery
    'A': 42, 'B': 40, 'C': 41, 'D': 41, 'E': 38, 'F': 35, 'G': 46.5,
    'H': 42, 'I': 15.5, 'J': 32.5, 'K': 44, 'L': 33, 'M': 48.5,
    'N': 41.5, 'O': 47, 'P': 41, 'Q': 46, 'R': 38, 'S': 40,
    'T': 38, 'U': 41, 'V': 39.5, 'W': 58, 'X': 40, 'Y': 39, 'Z': 36,
    # cyfry
    '0': 33, '1': 28, '2': 33, '3': 33, '4': 34, '5': 33,
    '6': 33, '7': 33, '8': 33, '9': 33,
    # znaki specjalne
    '#': 57.5, '.': 18.5, ':': 18.5, '-': 22, '(': 18.5, ')': 18.5,
    ' ': 16.5,
}

def calculate_width(text):
    """Oblicza sumę szerokości znaków w podanym tekście."""
    total = 0.0
    for ch in text:
        total += LETTER_WIDTHS.get(ch, 0.0)   # dla nieznanych znaków zwraca 0.0
    return total

@app.route('/', methods=['GET', 'POST'])
def index():
    result = None
    if request.method == 'POST':
        text = request.form.get('text', '')
        total_width = calculate_width(text)
        result = f'Długość napisu: {total_width:.1f} mm'
    return render_template('index.html', result=result)

if __name__ == '__main__':
    app.run(debug=True)