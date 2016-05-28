import rethinkdb as r

r.connect( "localhost", 28015).repl()

r.db("test").table_create("projects").run()

r.table("projects").insert([
    {
        "name": "Project #"+str(i),
        "versions": {
            "production": "1.2."+str(i),
            "staging": "1."+str(i+1),
            "testing": "0.0.0-feature-"+["backend", "db", "kubernetes", "cooladata"][i%4],
        }
    } for i in range(10)
]).run()
