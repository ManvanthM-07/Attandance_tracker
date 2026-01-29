from flask import Flask,render_template

app = Flask(_name_)

@app.route("/")
def hello_world():
    return render_template("index.html")
if _name_ == "_main_":
    app.run(debug=True)