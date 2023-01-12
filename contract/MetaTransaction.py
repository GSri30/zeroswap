import smartpy as sp

class MetaTransaction(sp.Contract):
    def __init__(self):
        # self.init(user_funds=sp.big_map(tkey=sp.TAddress, tvalue=sp.TRecord(contract_addr=sp.TAddress, amount=sp.TNat)))
        self.init(
            user_funds=sp.big_map(
                tkey=sp.TAddress, 
                tvalue=sp.TRecord(
                    amount=sp.TMutez, 
                    counter=sp.TNat
                )
            )
        )

    def get_counter(self, address):
        return self.data.user_funds.get(address,
            default_value=sp.record(amount=sp.tez(0), counter=0)
        ).counter

    def increment_counter(self, address):
        sp.if ~self.data.user_funds.contains(address):
            self.data.user_funds[address].counter = 0
        self.data.user_funds[address].counter += 1

    def get_address_from_pub_key(self, pub_key):
        return sp.to_address(sp.implicit_account(sp.hash_key(pub_key)))

    def transaction_verify(self, pub_key, signature, tx_expiry_time, sell_buy, amount):
        sp.set_type(pub_key, sp.TKey)
        sp.set_type(signature, sp.TSignature)
        sp.set_type(tx_expiry_time, sp.TTimestamp)

        sp_sender1 = sp.local("sp_sender1", 
            self.get_address_from_pub_key(pub_key)
        )
        counter = self.get_counter(sp_sender1.value)

        param_hash = sp.blake2b(
            sp.pack(
                sp.record(
                    sell_buy=sell_buy, 
                    amount=amount, 
                    tx_expiry_time=tx_expiry_time, 
                    chain_id=sp.chain_id, 
                    counter=counter
                )
            )
        )

        sp.verify(
            sp.check_signature(pub_key, signature, param_hash),
            "MISSIGNED"
        )
        return sp_sender1.value

    # @sp.private_lambda(with_storage="read-write", with_operations=True, wrap_call=True)
    # def transact(self, params):
    #     sp.set_type(
    #         params,
    #         sp.TRecord(
    #             destination=sp.TAddress,
    #             amount=sp.TMutez
    #         )
    #     )
    #     sp.send(params.destination, params.amount, message=None)

    @sp.entry_point
    def transaction_to_dex(self, params):
        sp.set_type(
            params, 
            sp.TRecord(
                pub_key=sp.TKey, 
                signature=sp.TSignature, 
                sell_buy=sp.TBool, 
                amount=sp.TMutez, 
                tx_expiry_time=sp.TTimestamp,
                # transaction=sp.TLambda(sp.TUnit, sp.TList(sp.TOperation))
            )
        )
        sp.verify(sp.now <= params.tx_expiry_time, "META_TX_EXPIRED")
        sp_sender = sp.local("sp_sender", sp.sender)

        sp_sender.value = self.transaction_verify(
            params.pub_key, 
            params.signature, 
            params.tx_expiry_time, 
            params.sell_buy, 
            params.amount
        )

        # transaction can be sent to dex
        sp.if params.sell_buy == True:
            self.data.user_funds[sp_sender.value].amount -= params.amount
            self.increment_counter(sp_sender.value)
            # sp.send(sp.self_address, sp.mutez(1000000), message=None)
            # params.transaction()
            # call dex contract to sell
        sp.if params.sell_buy == False:
            self.data.user_funds[sp_sender.value].amount += params.amount
            self.increment_counter(sp_sender.value)
            # transaction()
            # call dex contract to buy

    @sp.entry_point
    def withdraw(self, params):
        sp.set_type(
            params, 
            sp.TRecord(
                pub_key=sp.TKey, 
                signature=sp.TSignature, 
                sell_buy=sp.TBool, 
                amount=sp.TMutez, 
                tx_expiry_time=sp.TTimestamp
            )
        )

        sp.verify(sp.now <= params.tx_expiry_time, "META_TX_EXPIRED")
        sp_sender = sp.local("sp_sender", sp.sender)

        sp_sender.value = self.transaction_verify(
            params.pub_key, 
            params.signature, 
            params.tx_expiry_time, 
            params.sell_buy, 
            params.amount
        )

        # transaction can be sent to dex
        sp.if params.sell_buy == True:
            self.data.user_funds[sp_sender.value].amount -= params.amount
            self.increment_counter(sp_sender.value)
            # send tokens back to user


    @sp.entry_point
    def default(self, params):
        sp.set_type(params, sp.TUnit)
        sp.if ~self.data.user_funds.contains(sp.sender):
            self.data.user_funds[sp.sender]=sp.record(
                amount=sp.mutez(0), 
                counter=0
            )
        self.data.user_funds[sp.sender].amount += sp.amount
        self.data.user_funds[sp.sender].counter += 1
        

@sp.add_test(name="MetaTransaction")
def test():
    owner = sp.test_account("owner")
    alice = sp.test_account("alice")
    bob = sp.test_account("bob")
    carol = sp.test_account("carol")
    dex = sp.test_account("dex")
    server = sp.test_account("server")
    
    meta_tx = MetaTransaction()
    scenario = sp.test_scenario()
    scenario.h1("MetaTransaction")
    scenario += meta_tx

    # address1 = sp.
    
    scenario += meta_tx.default().run(sender=alice, amount=sp.mutez(1000000))
    scenario += meta_tx.default().run(sender=bob, amount=sp.mutez(1000000))
    scenario += meta_tx.default().run(sender=carol, amount=sp.mutez(1000000))

    signature = sp.make_signature(
        alice.secret_key, 
        sp.blake2b(
            sp.pack(
                sp.record(
                    sell_buy=True, 
                    amount=sp.mutez(100000),
                    tx_expiry_time=sp.timestamp_from_utc(2022, 11, 7, 12, 12, 12), 
                    chain_id=sp.chain_id, 
                    counter=1
                )
            )
        ), message_format="Raw")

    # op = sp.operations()
    

    # transact = sp.build_lambda(
    #     lambda sp.unit() : sp.operations(),
    #     with_storage=None, 
    #     with_operations=False, 
    #     recursive=False
    # )

    # sp.add_operations(sp.send(alice.address, sp.mutez(1000000)))
    
    scenario += meta_tx.transaction_to_dex(
        sp.record(
            pub_key=alice.public_key, 
            signature=signature, 
            tx_expiry_time=sp.timestamp_from_utc(2022, 11, 7, 12, 12, 12), 
            sell_buy=True, 
            amount=sp.mutez(100000),
            # transaction=transact(
            #     sp.unit(),
            #     sp.operations()
            # )
        )
    ).run(sender=server)
    
    scenario += meta_tx.transaction_to_dex(
        sp.record(
            pub_key=alice.public_key, 
            signature=signature, 
            tx_expiry_time=sp.timestamp_from_utc(2022, 11, 7, 12, 12, 12), 
            sell_buy=True, 
            amount=sp.mutez(100000)
        )
    ).run(sender=server, valid=False)

    signature2 = sp.make_signature(
        alice.secret_key, 
        sp.blake2b(
            sp.pack(
                sp.record(
                    sell_buy=True, 
                    amount=sp.mutez(100000),
                    tx_expiry_time=sp.timestamp_from_utc(2022, 11, 7, 12, 12, 12), 
                    chain_id=sp.chain_id, 
                    counter=2
                )
            )
        ), message_format="Raw")
    
    scenario += meta_tx.transaction_to_dex(
        sp.record(
            pub_key=alice.public_key, 
            signature=signature2, 
            tx_expiry_time=sp.timestamp_from_utc(2022, 11, 7, 12, 12, 12), 
            sell_buy=True, 
            amount=sp.mutez(100000)
        )
    ).run(sender=server)
