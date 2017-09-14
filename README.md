Set up for this is fairly simple. As always, you will first need to have installed Grakn (this was written on 0.15.0). 
If you're coming here from the blog, then you probably already have grakn installed, but if you don't, you can use something 
like Homebrew to quickly get up and running, using the command
```
brew install grakn
```
You will then have to go into the Grakn directory and start the Grakn shell script, like so
```
/YOUR-GRAKN-DIRECTORY/bin/grakn.sh start
```
This will allow you to make queries through the Graql shell

## Running the program
This was writeen on Python 3.6. Install all requirement with the `pip install -r requirements.txt` query and then run one of two queries to start the program

```
python ./domEncoder.py -e INSERT_URL_HERE
```

```
python ./domEncoder.py -d INSERT_KEY_HASH
```

You can only decode something after it's already been encoded and inserted into Grakn. The shell will spit out the hash of the URL, which you can then use with the `-d` flag to decode the graph and convert it back to HTML. 
-------------------------------------
Reminder that this program doesn’t always work for non XHTML documents (i.e. where XML rules do not apply). For example, `link` and `meta` tags (and several others) do not take a closing backslash in non-XML documents, so there is no end tag and the program thinks that every successive link is a level deeper in the DOM tree as a result. To fix this, you would need to recognize the type of document you have and whether these elements take end tags. 

