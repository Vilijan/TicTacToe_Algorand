# TicTacToe on the Algorand blockchain
In this solution I describe how you can develop the Tic-Tac-Toe game on the Algorand blockchain. The game logic is implemented as a [Stateful Smart Contract](https://developer.algorand.org/docs/features/asc1/stateful/) using [PyTeal](https://pyteal.readthedocs.io/en/latest/overview.html) while the communication with the network is done using the [py-algorand-sdk](https://github.com/algorand/py-algorand-sdk). 

Two players submit equal amount of algos to an escrow address which marks the start of the game. After this step, the players interchangeably place their marks on the board where the placing mark action is implemented as an application call to the Stateful Smart Contract. In the end whoever player wins the game is able to withdraw the funds submitted to the escrow address, in case of a tie both players are able to withdraw half of the amount submitted to the escrow address.

The goal of this solution is to present a starting point for developers to easily build board games as DApps on the Algorand Blockchain. The idea is that they should be able to change the game logic from Tic-Tac-Toe to whichever board game they prefer like Chess, Connect4, Go or others and deploy it on the network. 

# Environment setup

- `pip install -r requirements.txt`
- This solution uses PyTeal which compiles into TEAL 4. However as of time of writing this, the official version of PyTeal still does not support the TEAL 4. That is why I downloaded the [official repository](https://github.com/algorand/pyteal) and install it using `pip install -e .` in my current conda environment.
- Configure a `config.yml` file with the properties shown below:

```yaml
accounts:
  account_1:
    address: PUBLIC_KEY_VALUE
    mnemonic: MNEMONIC_WORDS
    private_key: PRIVATE_KEY_VALUE
  account_2:
    address: PUBLIC_KEY_VALUE
    mnemonic: MNEMONIC_WORDS
    private_key: PRIVATE_KEY_VALUE
  account_3:
    address: PUBLIC_KEY_VALUE
    mnemonic: MNEMONIC_WORDS
    private_key: PRIVATE_KEY_VALUE
  total: 3

client_credentials:
  address: ADDRESS_VALUE
  token: TOKEN_VALUE

```

# Deployment on Algorand TestNet

- Once you have setup your config file and funded the accounts that are specified in the config, you will be able to run the scripts: `player_x_win.py`, `player_o_win.py`, `tie_game.py` and `timeout_win.py`
- You can watch the following video that gives a short introduction to the solution as well as how you can play one TicTacToe game on the Algorand TestNet

[![Watch the video](https://github.com/Vilijan/TicTacToe_Algorand/blob/main/images/tictactoe_video_thumbnail.png?raw=true)](https://www.youtube.com/watch?v=S9I_74Hfg54&t=1s&ab_channel=VilijanMonev)
