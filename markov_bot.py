#! /usr/bin/env python
#
# Example program using irc.bot.
#
# Joel Rosdahl <joel@rosdahl.net>

"""A simple example bot.

This is an example bot that uses the SingleServerIRCBot class from
irc.bot.  The bot enters a channel and listens for commands in
private messages and channel traffic.

text sent in a pm will reply with a markov chain built off that text.

text in a public channel will be replied to 1/50 times with  a markov chain reply.
"""

import random
import sys
import irc.bot
import irc.strings
from irc.client import ip_numstr_to_quad, ip_quad_to_numstr
from pprint import pprint
import string

reload(sys)
sys.setdefaultencoding("utf-8")

class TestBot(irc.bot.SingleServerIRCBot):
    def __init__(self, channel, nickname, server, port=6667 ):
        irc.bot.SingleServerIRCBot.__init__(self, [(server, port)], nickname, nickname)
        self.channel = channel

    def on_nicknameinuse(self, c, e):
        c.nick(c.get_nickname() + "_")

    def on_welcome(self, c, e):
        c.join(self.channel) #chan pw can go here as 2nd arg

    def on_privmsg(self, c, e): 
        global markov_obj
        global table        
        #get message text
        message_words = e.arguments[0].lower().split()
        #find similarities in the tf-idf list
        similarity_list = table.similarities(message_words)
        #no match found, just do a random generation
        if not similarity_list:
            c.privmsg(e.source.split("!")[0] , filter(lambda x: x in string.printable, markov_obj.generate_markov_text()))
        #we found a word, lets build a chain off of that!
        else:
            seed_word = max( similarity_list, key=lambda l: l[1])[0]
            print "found matching word in tf-idf table: "+seed_word
            c.privmsg(e.source.split("!")[0] , filter(lambda x: x in string.printable, markov_obj.generate_markov_text_with_seed(seed_word)))
    
    def on_pubmsg(self, c, e):
        randnum = random.random();
        if randnum < 0.02:
            global markov_obj
            global table
        
            #get message text
            message_words = e.arguments[0].lower().split()
            #find similarities in the tf-idf list
            similarity_list = table.similarities(message_words)
            #no match found, just do a random generation
            if not similarity_list:
                #### THIS NEXT BIT IS CONFUSING, HERES THE BREAKDOWN!
                #
                #             -channel        -split the nick from hostmask
                #             |               |                   -append ':'
                #             |               |                   |       -remove non printables                    - gen markov text
                #             v               v                   v       v                                         v
                c.privmsg(self.channel, e.source.split("!")[0] + ": " + filter(lambda x: x in string.printable, markov_obj.generate_markov_text()))
            #we found a word, lets build a chain off of that!
            else:
                #find the word with the highest tf-idf value:
                seed_word = max( similarity_list, key=lambda l: l[1])[0]
                print "found matching word in tf-idf table: "+seed_word
                c.privmsg(self.channel, e.source.split("!")[0] + ": " + filter(lambda x: x in string.printable, markov_obj.generate_markov_text_with_seed(seed_word)))
        print(str(randnum))

##we markov'ing~~~

class Markov(object):
    
    def __init__(self, open_file):
        self.cache = {}
        self.open_file = open_file
        self.words = self.file_to_words()
        self.word_size = len(self.words)
        self.database()
        
    
    def file_to_words(self):
        self.open_file.seek(0)
        data = self.open_file.read()
        words = data.split()
        return words
        
    
    def triples(self):
        """ Generates triples from the given data string. So if our string were
                "What a lovely day", we'd generate (What, a, lovely) and then
                (a, lovely, day).
        """
        
        if len(self.words) < 3:
            return
        
        for i in range(len(self.words) - 2):
            yield (self.words[i], self.words[i+1], self.words[i+2])
            
    def database(self):
        for w1, w2, w3 in self.triples():
            key = (w1, w2)
            if key in self.cache:
                self.cache[key].append(w3)
            else:
                self.cache[key] = [w3]
                
    def generate_markov_text(self, size=10):
        seed = random.randint(0, self.word_size-3)
        seed_word, next_word = self.words[seed], self.words[seed+1]
        w1, w2 = seed_word, next_word
        gen_words = []
        i = 0
        gen_words.append(w1)
        while (not (gen_words[len(gen_words)-1].endswith("."))) or i < size:
            w1, w2 = w2, random.choice(self.cache[(w1, w2)])
            gen_words.append(w1)
            i += 1
        return ' '.join(gen_words)
    
    def generate_markov_text_with_seed(self, seed, size=10):
        #get list of seed index's
        seed_index_list = []
        for i in xrange(len(self.words)):
            if unicode(seed.lower()) == unicode(self.words[i].lower()):
                seed_index_list.append(i)

        seed_word, next_word = self.words[random.choice(seed_index_list)] , self.words[random.choice(seed_index_list)+1]
        w1, w2 = seed_word, next_word
        gen_words = []
        i = 0
        gen_words.append(w1)
        while (not (gen_words[len(gen_words)-1].endswith("."))) or i < size:
            w1, w2 = w2, random.choice(self.cache[(w1, w2)])
            gen_words.append(w1)
            i += 1
        return ' '.join(gen_words)

class tfidf:
    def __init__(self):
        self.weighted = False
        self.documents = []
        self.corpus_dict = {}

    def addDocument(self, doc_name, list_of_words):
        # building a dictionary
        doc_dict = {}
        for w in list_of_words:
            doc_dict[w] = doc_dict.get(w, 0.) + 1.0
            self.corpus_dict[w] = self.corpus_dict.get(w, 0.0) + 1.0

        # normalizing the dictionary
        length = float(len(list_of_words))
        for k in doc_dict:
            doc_dict[k] = doc_dict[k] / length

        # add the normalized document to the corpus
        self.documents.append([doc_name, doc_dict])

    def similarities(self, list_of_words):
        """Returns a list of all the [docname, similarity_score] pairs relative to a list of words."""

        # building the query dictionary
        query_dict = {}
        for w in list_of_words:
            query_dict[w] = query_dict.get(w, 0.0) + 1.0

        # normalizing the query
        length = float(len(list_of_words))
        for k in query_dict:
            query_dict[k] = query_dict[k] / length

        # computing the list of similarities
        sims = []
        for doc in self.documents:
            score = 0.0
            doc_dict = doc[1]
            for k in query_dict:
                if doc_dict.has_key(k):
                    score += (query_dict[k] / self.corpus_dict[k]) + (doc_dict[k] / self.corpus_dict[k])
                    sims.append([k, score])
        return sims

def main():
    ##display usage info
    if len(sys.argv) != 5:
        print("Usage: testbot <server[:port]> <channel> <nickname> <markov_file>")
        sys.exit(1)

    #get server / port
    s = sys.argv[1].split(":", 1)
    server = s[0]
    if len(s) == 2:
        try:
            port = int(s[1])
        except ValueError:
            print("Error: Erroneous port.")
            sys.exit(1)
    else:
        port = 6667
    #set the channel and nickname of the bot
    channel = sys.argv[2]
    nickname = sys.argv[3]

    #generate our markov chain object
    markov_file = open(sys.argv[4])
    global markov_obj
    markov_obj = Markov(markov_file)

    #make an tfidf from the markov chain document for message analysis
    global table 
    table = tfidf()
    markov_file.seek(0)
    table.addDocument("markovDoc", markov_file.read().lower().split())

    #start shit on irc :)
    bot = TestBot(channel, nickname, server, port)
    bot.start()

if __name__ == "__main__":
    main()

