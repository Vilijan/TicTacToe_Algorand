from src.blockchain_utils.credentials import get_client, get_account_credentials
from src.services.game_engine_service import GameEngineService

client = get_client()

acc_pk, acc_address, _ = get_account_credentials(account_id=3)
player_x_pk, player_x_address, _ = get_account_credentials(account_id=1)
player_o_pk, player_o_address, _ = get_account_credentials(account_id=2)

game_engine = GameEngineService(app_creator_pk=acc_pk,
                                app_creator_address=acc_address,
                                player_x_pk=player_x_pk,
                                player_x_address=player_x_address,
                                player_o_pk=player_o_pk,
                                player_o_address=player_o_address)

game_engine.deploy_application(client=client)
game_engine.start_game(client=client)

game_actions = [
    ("X", 0),
    ("O", 1),
    ("X", 2),
    ("O", 4),
    ("X", 3),
    ("O", 5),
    ("X", 7),
    ("O", 6),
    ("X", 8),
]

for player_id, action_position in game_actions:
    game_engine.play_action(client=client,
                            player_id=player_id,
                            action_position=action_position)


game_engine.fund_escrow(client=client)
game_engine.tie_money_refund(client=client)

