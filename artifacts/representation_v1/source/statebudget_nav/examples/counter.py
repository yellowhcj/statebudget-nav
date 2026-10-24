"""API example only: turn with a one-byte, explicitly charged step counter."""

def step(frame,state,spec):
    counter=(state[0] if state else 0)
    return counter%2,bytes([(counter+1)%256]),dict(counter=counter)
