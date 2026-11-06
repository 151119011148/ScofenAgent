import gradio as gr

with gr.Blocks() as demo:
    r = gr.Radio(choices=[("甲", "A"), ("乙", "B"), ("丙", "C")], value="A", label="r")
    ch = gr.Textbox(value="ch-start", label="chg", elem_id="chg")
    ip = gr.Textbox(value="ip-start", label="inp", elem_id="inp")
    st = gr.Textbox(value="st-start", label="set", elem_id="st")
    r.change(lambda v, l: (l or "") + "|change:%r" % (v,), [r, ch], ch)
    r.input(lambda v, l: (l or "") + "|input:%r" % (v,), [r, ip], ip)
    r.select(lambda v, l: (l or "") + "|select:%r" % (v,), r, st)
    gr.Button("set-to-B", elem_id="set-b").click(lambda: gr.update(value="B"), None, r)
    gr.Button("set-to-None", elem_id="set-none").click(lambda: gr.update(value=None), None, r)

demo.launch(share=False, server_name="127.0.0.1", server_port=7862)
