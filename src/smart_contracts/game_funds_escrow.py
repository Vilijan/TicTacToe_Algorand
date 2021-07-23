from pyteal import *


def game_funds_escorw(app_id: int):

    win_refund = Seq([
        Assert(Gtxn[0].application_id() == Int(app_id)),
        Assert(Gtxn[1].fee() <= Int(1000)),
        Assert(Gtxn[1].asset_close_to() == Global.zero_address()),
        Assert(Gtxn[1].rekey_to() == Global.zero_address())
    ])

    tie_refund = Seq([
        Assert(Gtxn[0].application_id() == Int(app_id)),
        Assert(Gtxn[1].fee() <= Int(1000)),
        Assert(Gtxn[1].asset_close_to() == Global.zero_address()),
        Assert(Gtxn[1].rekey_to() == Global.zero_address()),
        Assert(Gtxn[2].fee() <= Int(1000)),
        Assert(Gtxn[2].asset_close_to() == Global.zero_address()),
        Assert(Gtxn[2].rekey_to() == Global.zero_address())
    ])

    return Seq([
        Cond(
            [Global.group_size() == Int(2), win_refund],
            [Global.group_size() == Int(3), tie_refund],
        ),
        Return(Int(1))
    ])

