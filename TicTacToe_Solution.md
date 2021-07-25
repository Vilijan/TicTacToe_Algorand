# Overview

In this solution I describe how you can develop the Tic-Tac-Toe game on the Algorand blockchain. The game logic is implemented as a [Stateful Smart Contract](https://developer.algorand.org/docs/features/asc1/stateful/) using [PyTeal](https://pyteal.readthedocs.io/en/latest/overview.html) while the communication with the network is done using the [py-algorand-sdk](https://github.com/algorand/py-algorand-sdk). 

Two players submit equal amount of algos to an escrow address which marks the start of the game. After this step, the players interchangeably place their marks on the board where the placing mark action is implemented as an application call to the Stateful Smart Contract with the desired position passed as an argument. In the end whoever player wins the game is able to withdraw the funds submitted to the escrow address, in case of a tie both players are able to withdraw half of the amount submitted to the escrow address.

The goal of this solution is to present a starting point for developers to easily build board games as DApps on the Algorand Blockchain. The idea is that they should be able to change the game logic from Tic-Tac-Toe to whichever board game they prefer like: Chess, Connect4, Go or others and deploy it on the network.

# Application architecture

The Tic-Tac-Toe decentralized application has two main components:

1. **Smart contracts** - this component contains all of the PyTeal code divided into two submodules:
   - Tic-Tac-Toe ASC1 - this stateful smart contract implements the game logic and defines the interaction between the players and the application. There are 3 possible interactions with this smart contract: starting the game, executing game action and refunding the submitted Algos by the players.
   - Escrow fund - this is a [stateless smart contract](https://developer.algorand.org/docs/features/asc1/stateless/) that holds the funds submitted by the players on game start. This escrow address is linked to the Tic-Tac-Toe ASC1. On game end, the escrow fund is responsible to make the appropriate refunding of the submitted algos.
2. **Game Engine service** - this is the submodule which is responsible for submitting the right transactions to the network in order to interact with the smart contracts. Those are the following services that are implemented by the game engine:
   - Application deployment - creates an application create transaction and deploys the Tic-Tac-Toe ASC1 to the network.
   - Start game - submits an [atomic transfer](https://developer.algorand.org/docs/features/atomic_transfers/) of 3 transaction to the network in order to denote the start of the game. 
   - Play action - submits a single application call transaction to the Tic-Tac-Toe ASC1 which executes a move in the game.
   - Win refund - submits an atomic transfer of 2 transactions to the network that refunds the algos to the winner of the game.
   - Tie refund - submits an atomic transfer of 3 transactions to the network that refunds the algos to the both players of the game.

# State representation and transition

In order to optimize the state representation and state transitions in the Tic-Tac-Toe DApp I decided to implement them as bitmasks and use [bit manipulations](https://en.wikipedia.org/wiki/Bit_manipulation) for the state transitions. 

The game state is represented as two separate integer variables *state<sub>x</sub>* and *state<sub>o</sub>*. If the *i<sup>th</sup>* bit in the state<sub>x</sub> is on it means that there is a "X" mark at position *i* in the board, while on the other hand if the  *i<sup>th</sup>* bit in the state<sub>o</sub> is active it means that there is a "O" mark at position *i*. The board positions are enumerated from 0 to 8 left to right, while the top left position is numbered with 0 while the bottom right position is numbered with 8. On the following image you can see an image that describes the state representation of the Tic-Tac-Toe game using two bit masks:

![State representation](https://github.com/Vilijan/TicTacToe_Algorand/blob/main/images/state_representation.png?raw=true)

On the image above we can see how we have decoupled the original Tic-Tac-Toe game state into two separate integer states using bitmasks.





# Tic-Tac-Toe ASC1

In this section I will explain in more details the logic behind the PyTeal [source code](https://github.com/Vilijan/TicTacToe_Algorand/blob/main/src/smart_contracts/tic_tac_toe_asc1.py) in the Tic-Tac-Toe ASC1. The application has 9 global variables shown in the code snippet below:

```python
class AppVariables:
    PlayerXState = Bytes("PlayerXState")
    PlayerOState = Bytes("PlayerOState")

    PlayerOAddress = Bytes("PlayerOAddress")
    PlayerXAddress = Bytes("PlayerXAddress")
    PlayerTurnAddress = Bytes("PlayerTurnAddress")
    FundsEscrowAddress = Bytes("FundsEscrowAddress")

    BetAmount = Bytes("BetAmount")
    ActionTimeout = Bytes("ActionTimeout")
    GameStatus = Bytes("GameState")

    @classmethod
    def number_of_int(cls):
        return 5

    @classmethod
    def number_of_str(cls):
        return 4
```

- PlayerXState and PlayerOState - those are integer variables that represent the game board for each of the players. The state representation was described in more details in the previous section.
- PlayerXAddress and PlayerOAddress - those variables represent the addresses for each of the players. They are initialized when the start game action is performed.
- PlayerTurnAddress - this variable represents the address of the player who needs to place the next mark on the board. The game always starts with the PlayerXAddress and the PlayerTurnAddress is changed on every game action because the players place marks interchangeably. 
- FundsEscrowAddress - this variable represents the escrow address who is responsible for holding the funds submitted by the players. This address is initialized on the start game action as well. 
- BetAmount - represents the amount of micro algost that each player needs to submit to the escrow address.
- ActionTimeout - represents for how many seconds the game will be active on the Algorand blockchain. If the player whose turn it is hasn't played an action in the specified timeout interval the other player will be declared as a winner and will be able to withdraw the funds from the escrow address.
- GameStatus - is an integer variable that represents the current status of the game.
  - 0 - means that the game is active and the players are currently interacting with it.
  - 1 - means that the game was won by player X.
  - 2 - means that the game was won by player O.
  - 3 - means that the game ended with a tie.



