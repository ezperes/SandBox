""" M00002_TradeSensor Module

    Bears the class TradeSensor, corresponding to functionality ft0002_TradeSensor within
    The Dream Company Trading Ecosystem - TradeEco

    PURPOSE
    To provide sensitiveness for the occurance of a trade event, regarding a given OrderActuator
    """


class TradeSensor:
    """
    PURPOSE
        - To provide sensitiveness for the occurance of a trade event, regarding a given OrderActuator.

    FUNCTIONALITY MECHANISM
        - Once upon a regular time basis, cicles through all orders in OrderActuator
            - Access the order's account, checking whether there is change in it's trade history.
              If no change in history, pass.
                - If there is new history entry, checks whether it is "order fill" type. If not, pass.
                    - If it is order fill type:
                        - Commands OrderActuator to update the FILLED amount of lots,and its further consequences
                            (e.g.: if order is fully filled, marks it as full filled).
                        - Updates local history and its consequences.
                        - Calls OnTrade of interested subscriber.
        - AGENTS interested on listening to this sensor MUST SUBSCRIBE it once upon its initialization.
            - Such AGENTS *Must* have a method named "OnTrade" so it shall be called opportunately

    USABILITY REQUIREMENTS
        - On initialization, must receive and store in an "attribute" the OrderActuator object which bears all orders marked as "not filled" within
        TradEco, so they can be cycled through
            - The orders must be in a dictionary of type { order_id:int : order_object, }
        - Must have a time interval attribute to cycle



    """
    pass
