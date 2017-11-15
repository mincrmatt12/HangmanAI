# HangmanAI

A computer program that plays hangman.

Not exactly very well coded, but if you have pygame installed and want to put a word in to my program do this:

## Usage

Using the program is fairly simple. A lot of the other scripts in the repo created helper files.

### Steps

- Run wordcount.py
- Enter the length of the word in the console
- Wait for it to process
- Using the interface, play hangman

### UI

On the screen, the controls are left and right move along the word. Pushing a key sets the letter there to what you pushed. Pushing backspace sets it back to a -
The AI's guess is also shown. Use space to toggle if it was correct or not. Press enter to get the next guess.

## Limitations

The program can only guess words in its dictionary. If you input a word not in its dictionary, when it realizes it will crash due to
there being no valid predictions, and so it can't make a guess.
