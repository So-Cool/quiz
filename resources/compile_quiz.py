#!/usr/bin/env python

# Update brief.html, wiki, readme, gh-pages
# Update question requirements

import re
import sys, os, shutil
import json
import argparse
import tarfile
from html_templates import questionCategories,questionTemplate,quizTemplate
from html_templates import singleTemplate
from html_templates import sortTemplate
from html_templates import matrixSort_answers_single,matrixSort_question_single,matrixSort_questionTemplate
from html_templates import tableTemplate
from html_templates import blankItem,blankTemplate
from html_templates import multipleTemplate
from html_templates import iframeGeneralTemplate, iframeIframeTemplate

# command line arguments parser
parser = argparse.ArgumentParser(description='Simple quiz generator.')
parser_group1 = parser.add_mutually_exclusive_group()
parser_group1.add_argument('-q', '--question', type=int, nargs=1, required=False, dest="question", default=None, help=('the # of question to be generated (all questions are generated by default)'))
parser_group1.add_argument('-a', '--all', required=False, dest="all", default=True, action='store_true', help=('generate all of the questions'))
parser_group1.add_argument('-s', '--separate', required=False, dest="separate", default=False, action='store_true', help=('generate all of the questions in separate files'))
parser_group1.add_argument('-i', '--iframe', required=False, dest="iframe", default=False, action='store_true', help=('generate all of the question on one page (iframe)'))

parser_group2 = parser.add_mutually_exclusive_group()
parser_group2.add_argument('-o', '--order', required=False, dest="order", default=False, action='store_true', help=('order the questions first on book section then on difficulty'))
parser_group2.add_argument('-O', '--Order', required=False, dest="Order", default=False, action='store_true', help=('order the questions first on difficulty then on book section'))

parser.add_argument('-d', '--debug', required=False, dest="debug", default=False, action='store_true', help=('indicate the correct answer in the question'))
parser.add_argument('--comments', required=False, dest="comments", default=False, action='store_true', help=('show *comments* in each question'))
parser.add_argument('--hints', required=False, dest="hints", default=False, action='store_true', help=('show *hints* in each question'))
parser.add_argument('--source', required=False, dest="source", default=False, action='store_true', help=('show *source* in each question'))
parser.add_argument('--workings', required=False, dest="workings", default=False, action='store_true', help=('show *workings* in each question'))
parser.add_argument('--explanation', required=False, dest="explanation", default=False, action='store_true', help=('show *explanation* in each answer'))
parser.add_argument('-f', '--feedback', required=False, dest="feedback", default=False, action='store_true', help=('generate feedback for all questions'))
parser.add_argument('-e', '--extract', required=False, dest="extract", default=False, action='store_true', help=('export marked questions to separate file'))
parser.add_argument('-c', '--count', required=False, dest="count", default=False, action='store_true', help=('show difficulty statistics of the quiz file'))

parser.add_argument('-t', '--tarball', required=False, dest="tarball", default=False, action='store_true', help=('tarball the quiz for submissions'))
parser.add_argument('-p', '--peter', required=False, dest="peter", default=False, action='store_true', help=('Peter\'s special 1'))
parser.add_argument('-P', '--Peter', required=False, dest="Peter", default=False, action='store_true', help=('Peter\'s special 2'))

parser.add_argument('filename', type=str, nargs=1, help='path to your `.quiz` file')

#
# answer contingency table regex
#
mx_rx = re.compile(r"""
  # parse matrix in form of
  #
  # 00 | 01 | 02
  # ------------
  # 10 | 11 | 12
  # ------------
  # 20 | 21 | 22
  #
  \s*(?P<oo>\d+)\s*\|\s*(?P<oi>\d+)\s*\|\s*(?P<oz>\d+)\s*(\n|\r\n)
  -+(\n|\r\n)
  \s*(?P<io>\d+)\s*\|\s*(?P<ii>\d+)\s*\|\s*(?P<iz>\d+)\s*(\n|\r\n)
  -+(\n|\r\n)
  \s*(?P<zo>\d+)\s*\|\s*(?P<zi>\d+)\s*\|\s*(?P<zz>\d+)\s*
""", re.X | re.M)

# debug answers
ANSWERS_DEBUG = False
SHOW_HINTS = False
SHOW_COMMENTS = False
SHOW_SOURCE = False
SHOW_WORKINGS = False
SHOW_EXPLANATION = False

def add_hint_comment(ctype, comment):
  colour_box = '<p style="border-style:solid; border-width:5px; border-color:#ff0000 #0000ff;">%s:<br>%s</p><hr>'
  if ctype == 'c':
    return colour_box % ("comment", comment)
  elif ctype == 'h':
    return colour_box % ("hint", comment)
  elif ctype == 's':
    return colour_box % ("source", comment)
  elif ctype == 'w':
    return colour_box % ("workings", comment)
  elif ctype == 'e':
    return colour_box % ("explanation", comment)

#
# correct answer indicator
#
def markAnswerCh(answerText):
  return "&laquo;" + " " + answerText
def markAnswerOr(answerText, order):
  return str(order) + "" + "&laquo;" + " " + answerText
def markBlank(answerText):
  return "&raquo;" + answerText + "&laquo;" + " "

#
# blanks converter
#
def mergeBlanks(textList, answers):
  answer = ""
  for i in textList:
    if type(i) == int:
      answer += "[answer]" + answers[i] + "[/answer]"
    elif type(i) == str or type(i) == unicode:
      answer += i
    else:
      print( "Unknown prompt type!" )
      sys.exit(1)
  return answer
def fillBlanks(textList, dictionaryAnswers):
  qs = ""
  for i in textList:
    if type(i) == int:
      qs += ( blankItem % dictionaryAnswers[i] )
    elif type(i) == str or type(i) == unicode:
      qs += i
    else:
      print( "Unknown prompt type!" )
      sys.exit(1)
  return qs

def parseQuestions(filename):
  ########################################
  # http://stackoverflow.com/questions/956867/how-to-get-string-objects-instead-of-unicode-ones-from-json-in-python
  def json_load_byteified(file_handle):
    return _byteify(
      json.load(file_handle, object_hook=_byteify),
      ignore_dicts=True
    )

  def json_loads_byteified(json_text):
    return _byteify(
      json.loads(json_text, object_hook=_byteify),
      ignore_dicts=True
    )

  def _byteify(data, ignore_dicts = False):
    # if this is a unicode string, return its string representation
    if isinstance(data, unicode):
      return data.encode('utf-8')
    # if this is a list of values, return list of byteified values
    if isinstance(data, list):
      return [ _byteify(item, ignore_dicts=True) for item in data ]
    # if this is a dictionary, return dictionary of byteified keys and values
    # but only if we haven't already byteified it
    if isinstance(data, dict) and not ignore_dicts:
      return {
          _byteify(key, ignore_dicts=True): _byteify(value, ignore_dicts=True)
          for key, value in data.iteritems()
      }
    # if it's anything else, return it in its original form
    return data
  ########################################


  with open(filename, 'r') as quiz_file:
    quiz_text = quiz_file.read()

  # remove comments from quiz file
  quiz_text = re.sub(r'^\s*//.+$', "", quiz_text, flags=re.M)

  # merge lines ended with "\": allow multiline in strings
  quiz_text = re.sub(r'\\$\s*', "", quiz_text, flags=re.M)

  # read in JSON
  # quiz_text = json.loads(quiz_text)
  quiz_text = json_loads_byteified(quiz_text)

  # find the parent url
  url = quiz_text.get('url', '')

  # find title for quiz
  title = quiz_text.get('title', '')

  # find candidate ids
  uid = quiz_text.get("candidate_number", [])
  if not uid:
    sys.exit("Candidate number not supplied. It's required for this assignment")
  uid = [str(i) for i in uid]

  # find all questions
  questions = {i:quiz_text[i] for i in quiz_text if i.strip().isdigit()}

  results = []
  question_indeces = []

  difficulty_count = [0, 0, 0, 0, 0]
  used_sections = []
  unique_sections = 0

  for q in questions:
    out = {}

    out['fullq'] = json.dumps(questions[q], sort_keys=True, indent=4)

    out['number'] = int(q)
    if out['number'] in question_indeces:
      print("Question index: " + str(out['number'] + " repeated"))
      sys.exit(1)
    question_indeces.append(out['number'])

    out['answer_type'] = questions[q].get('answer_type', '').strip()
    if not out['answer_type'] :
      sys.exit("Answer type (not given for question #%d" % out['number'])
    if out['answer_type'] not in ['single', 'multiple', 'sort', \
                                  'blank_answer', 'cloze_answer', \
                                  'matrix_sort_answer']:
      sys.exit("Unknown answer type \"%s\" for question #%d" % \
               (out['answer_type'], out['number'])
              )

    out['problem_type'] = questions[q].get('problem_type', '').strip()
    if not out['problem_type']:
      sys.exit("Problem type not given for question #%d" % out['number'])

    out['comments'] = questions[q].get('comments', '').strip()
    if not out['comments']:
      sys.exit("Comments not given for question #%d" % out['number'])

    out['source'] = questions[q].get('source', '').strip()
    if not out['source']:
      sys.exit("Source not given for question #%d" % out['number'])

    out['hint'] = questions[q].get('hint', '').strip()
    if not out['hint']:
      sys.exit("Hint not given for question #%d" % out['number'])

    out['workings'] = questions[q].get('workings', '').strip()
    # if not out['workings']:
    #   sys.exit("Workings not given for question #%d" % out['number'])

    book = questions[q].get('reference', '')
    book_split = book.split('.')
    if len(book_split) != 2:
        sys.exit('Incorrect book reference format \"%s\" in question #%d' % \
                 (book, out['number'])
                )
    if not book_split[0].isdigit():
        sys.exit('Incorrect format of book chapter \"%s\" in question #%d' % \
                 (book_split[0].strip(), out['number'])
                )
    if int(book_split[0]) not in questionCategories:
        sys.exit('Unknown book chapter \"%s\" in question #%d' % \
                 (book_split[0].strip(), out['number'])
                )
    out['chapter'] = int(book_split[0])
    if not book_split[1].isdigit():
        sys.exit('Incorrect format of book section \"%s\" in question #%d' % \
                 (book_split[1].strip(), out['number'])
                )
    if int(book_split[1]) not in questionCategories[out['chapter']]:
        sys.exit('Unknown book section \"%s\" in question #%d' % \
                 (book_split[1].strip(), out['number'])
                )
    out['section'] = int(book_split[1])

    # count unique sections
    current_section = str(out['chapter']) + "." + str(out['section'])
    if current_section not in used_sections:
      used_sections.append(current_section)
      unique_sections += 1

    difficulty = questions[q].get('difficulty', '').strip()
    if not difficulty:
        sys.exit('Difficulty not given in question #%d' % out['number'])
    if difficulty not in ["1", "2", "3", "4", "5"]:
        sys.exit('Unknown difficulty \"%s\" in question #%d' % \
                 (difficulty, out['number'])
                )
    out['difficulty'] = difficulty

    # count difficulties
    if out['difficulty'] == "5":
      difficulty_count[0] += 1
    elif out['difficulty'] == "4":
      difficulty_count[1] += 1
    elif out['difficulty'] == "3":
      difficulty_count[2] += 1
    elif out['difficulty'] == "2":
      difficulty_count[3] += 1
    elif out['difficulty'] == "1":
      difficulty_count[4] += 1

    if out['answer_type'].lower() == 'single' or \
       out['answer_type'].lower() == 'multiple' or \
       out['answer_type'].lower() == 'sort' or \
       out['answer_type'].lower() == 'cloze_answer' or \
       out['answer_type'].lower() == 'matrix_sort_answer':

      out['prompt'] = questions[q].get('question', '').strip()
      if not out['prompt']:
        sys.exit('Question not given in question #%d.' % out['number'])
      if SHOW_COMMENTS:
        out['prompt'] = add_hint_comment('c', out['comments']) + out['prompt']
      if SHOW_HINTS:
        out['prompt'] = add_hint_comment('h', out['hint']) + out['prompt']
      if SHOW_WORKINGS:
        out['prompt'] = add_hint_comment('w', out['workings']) + out['prompt']
      if SHOW_SOURCE:
        out['prompt'] = add_hint_comment('s', out['source']) + out['prompt']

      out['answers'] = []
      out['correct'] = []
      out['explanation'] = []
      # single, multiple, sort, matrix_sort_answer
      if isinstance(questions[q].get('answers'), list):
        for i, a in enumerate(questions[q].get('answers', [])):
          # single, multiple
          if a['correctness'] == "+" or a['correctness'] == "-":
            out['answers'].append(a['answer'].strip())
            if a['correctness'] == "+":
              explanation = a.get('explanation', '').strip()
              if not explanation:
                sys.exit('Explanation missing in question #%d answer %d' % (out['number'], i))
              out["explanation"].append((i, explanation))
              out['correct'].append(i)
              # if answer debug flag is set append correct answer indicator
              if ANSWERS_DEBUG:
                out['answers'][i] = markAnswerCh(out['answers'][i])
              if SHOW_EXPLANATION:
                out['answers'][i] += add_hint_comment("e", explanation)
          # sort
          elif a['correctness'].isdigit():
            out['answers'].append(a['answer'].strip())
            out['correct'].append(int(a['correctness']))

            explanation = a.get('explanation', '').strip()
            if not explanation:
              sys.exit('Explanation missing in question #%d answer %s' % (out['number'], out['correct'][-1]))
            out["explanation"].append((out['correct'][-1], explanation))

            # if answer debug flag is set append correct ordering
            if ANSWERS_DEBUG:
              out['answers'][i] = markAnswerOr(out['answers'][i],
                                               out['correct'][-1])
            if SHOW_EXPLANATION:
              out['answers'][i] += add_hint_comment("e", explanation)
          # matrix_sort_answer
          elif (isinstance(a['correctness'], str) or \
                isinstance(a['correctness'], unicode)) and \
               len(a['correctness']) > 1:
            out['correct'].append(a['answer'].strip())

            explanation = a.get('explanation', '').strip()
            if not explanation:
              sys.exit('Explanation missing in question #%d answer %s' % (out['number'], i))
            out["explanation"].append((i, explanation))

            if ANSWERS_DEBUG:
              out['answers'].append(a['correctness'].strip() + " " + \
                                    markBlank(a['answer'].strip()))
            else:
              out['answers'].append(a['correctness'].strip())
            if SHOW_EXPLANATION:
              out['answers'][i] += add_hint_comment("e", explanation)
      # contingency table
      elif isinstance(questions[q].get('answers'), dict):
        out['answers'] = None
        explanation = a.get('explanation', '').strip()
        if not explanation:
          sys.exit('Explanation missing in question #%d' % out['number'])
        out['explanation'] = [explanation]

        if SHOW_EXPLANATION:
          out["prompt"] += add_hint_comment("e", explanation)

        answer = "\n".join(questions[q].get('answers', {}).get('answer', []))
        answer += "\n"
        try:
          answers = [m.groupdict() for m in mx_rx.finditer(answer)][0]
        except:
          sys.exit("Answers not given or malformed (contingency table) for \
                   question #%d" % out['number'])
        # reformat output
        out['correct'] = {00:answers['oo'], 01:answers['oi'], 02:answers['oz'],
                          10:answers['io'], 11:answers['ii'], 12:answers['iz'],
                          20:answers['zo'], 21:answers['zi'], 22:answers['zz']}
    elif out['answer_type'].lower() == 'blank_answer':
      out['answers'] = None
      out['correct'] = []
      out['explanation'] = []

      prompt = questions[q].get('question', [])
      if not prompt:
        sys.exit('Question not given in question #%d.' % out['number'])

      answer = {}
      for a in questions[q].get("answers", []):
        explanation = a.get('explanation', '').strip()
        if not explanation:
          sys.exit('Explanation missing in question #%d' % out['number'])
        answer[a["correctness"]] = a["answer"]
        out['explanation'].append((a["correctness"], explanation))

      out['prompt'] = []
      if SHOW_COMMENTS:
        out['prompt'] += [add_hint_comment('c', out['comments'])]
      if SHOW_HINTS:
        out['prompt'] += [add_hint_comment('h', out['hint'])]
      if SHOW_WORKINGS:
        out['prompt'] += [add_hint_comment('w', out['workings'])]
      if SHOW_SOURCE:
        out['prompt'] += [add_hint_comment('s', out['source'])]
      for a in prompt:
        if isinstance(a, str) or isinstance(a, unicode):
          out['prompt'].append(a)
        if isinstance(a, int):
          if ANSWERS_DEBUG:
            out['prompt'].append(markBlank(answer[a]))
          out['prompt'].append(len(out['correct']))
          out['correct'].append(answer[a])

      if SHOW_EXPLANATION:
        hhs = []
        for hh in out["explanation"]:
          hhs.append("%s blank: %s" % hh)
        out["prompt"] += add_hint_comment("e", "<br>".join(hhs))
    else:
      sys.exit("Unrecognised type of question: \"%s\" in question #%d." % \
               (out['answer_type'], out['number']))

    out['captions'] = []
    out['images'] = []
    im = questions[q].get('images', [])
    for a in im:
      out['captions'].append(a.get('caption', '').strip())
      out['images'].append(a['url'].strip())

    results.append(out)

  return(results, title, url, uid, unique_sections, difficulty_count)

# return HTML image environment
def insertImage(path, caption):
  return "<br><figure><img src=\"" + path + "\" /><figcaption>" + caption + "</figcaption></figure>"

# This function generates the JSON code that is required for the quiz
# library to grade the quizzes
def htmlToJson(question):
  json = {
    "type"   : question["answerType"],
    "id"     : question["id"],
    "catId"  : 0,
    "points" : 1,
    "correct": question["correctness"]
  }
  return json

# prepare and write results to html file
def toHtml(filename, results, title, qToGen):
  translate_difficulty = {"1":"easy (1)", "2":"easy-medium (2)", \
                          "3":"medium (3)", "4":"medium-hard (4)", \
                          "5":"hard (5)"}
  # skip all the other questions if only interested in one
  separateFilenames = False
  if type(qToGen) == list:
    for r in results:
      if qToGen[-1] == r['number']:
        resultsU = [r]
        resultPartition = [resultsU]
        break
  elif qToGen == None:
    resultsU = results
    resultPartition = [resultsU]
  elif qToGen:
    separateFilenames = True
    resultPartition = [[r] for r in results]
  else:
    sys.error("I shouldn't be here")

  # memorise question filenames if generating separately
  Qfilenames = []

  for rU in resultPartition:
    questions = []
    jsons = {}
    for result in rU:
      question = {}
      question["questionNumber"] = question["id"] = result['number']
      question["category"]       = str(result['chapter']) + "." + str(result['section']) +\
        ": " +  questionCategories[result['chapter']][0] + " : " +\
        questionCategories[result['chapter']][result['section']]
      question["difficulty"]     = translate_difficulty[result['difficulty']]

      # prepare question to display: text + images
      question["question"]       = result['prompt']
      for i in range(len(result['images'])):
        question["question"] += insertImage(result['images'][i], result['captions'][i])

      if result['answer_type'] == 'single':
        # Loop over the answers and extract the text if it has been filled in
        # appropriately remodel answers so that the first one in the list is
        # correct
        # TODO: fix in the same way as in multiple answers
        rAnswers = result['answers'][:]
        rAnswers_c = rAnswers.pop(result['correct'][0])
        rAnswers.insert(0, rAnswers_c)
        answers = []
        for ai, answer in enumerate(rAnswers):
          answers.append( dict(
            answerPos_0 = ai,
            answerPos_1 = ai + 1,
            id = question["id"],
            answerText = answer) )

        question["answers"] = answers

        question["correctness"] = [0] * len( question["answers"] )
        question["correctness"][0] = 1

        question["answersStr"] = "\n".join( singleTemplate % answer for answer in answers )
        question["numAnswers"] = len( answers )
        question["answerType"] = result['answer_type']
        question["json"] = htmlToJson( question )
        question["questionHTML"] = questionTemplate % question
      elif result['answer_type'] == 'multiple':
        answers = []
        for ai, answer in enumerate(result['answers']):
          answers.append( dict(
            answerPos_0 = ai,
            answerPos_1 = ai + 1,
            id = question["id"],
            answerText = answer) )
        question["answers"] = answers

        question['correctness'] = [0] * len( question["answers"] )
        for ri in result['correct']:
          question["correctness"][ri] = 1

        question["answersStr"] = "\n".join( multipleTemplate% answer for answer in answers )
        question["numAnswers"] = len( answers )
        question["answerType"] = result['answer_type']
        question["json"] = htmlToJson( question )
        question["questionHTML"] = questionTemplate % question
      elif result['answer_type'] == 'sort':
        answers = []
        for ai, answer in enumerate(result['answers']):
          answers.append( dict(
            answerPos_0 = ai,
            answerPos_1 = ai + 1,
            id = question["id"],
            answerText = answer) )
        question["answers"] = answers

        question["correctness"] = result['correct']

        question["answersStr"] = "\n".join( sortTemplate% answer for answer in answers )
        question["numAnswers"] = len( answers )
        question["answerType"] = result['answer_type']
        question["json"] = htmlToJson( question )
        question["questionHTML"] = questionTemplate % question
      elif result['answer_type'] == 'blank_answer':
        # overwrite the question prompt
        question["question"] = "Fill in the blanks"
        question["rawQuestion"] = mergeBlanks(result['prompt'], result['correct'])

        # Build up the dictionary of answers
        question["answers"] = []
        question["correctness"] = []
        for ic in result['correct']:
          ic_r = ic.split(',')
          ic_r = [r.strip() for r in ic_r]
          question["correctness"].append(ic_r)
          question["answers"].append({'length':max(map(len,ic_r)), 'answers':"("+', '.join(ic_r)+")"})

        questionStr = fillBlanks(result['prompt'], question["answers"])

        question["answerType"] = result['answer_type']
        question["numAnswers"] = len( question["answers"] )
        question["json"] = htmlToJson( question )
        question["answersStr"] = str( blankTemplate % questionStr )

        question["questionHTML"] = questionTemplate % question
      elif result['answer_type'] == 'cloze_answer':
        answers = []
        question["correctness"] = []
        # get dictionary keys and order them
        answerKeys = result['correct'].keys()
        answerKeys.sort()
        for ai, answer in enumerate( answerKeys ):
          answerText = str( result['correct'][answer] )
          question["correctness"].append( answerText )
          answers.append( dict( answerPos_0 = ai,
            answerPos_1 = ai + 1,
            id = question["id"],
            answerText = answerText ) )
        # Populate the question dict with the answers provided
        question["answerType"] = result['answer_type']
        question["answers"] = answers
        question["numAnswers"] = len( answers )
        question["json"] = htmlToJson( question )
        # decide on template to fill based on debugging state
        template = None
        if ANSWERS_DEBUG:
          marked = [markBlank(x) for x in question["correctness"]]
          template = [x for pair in zip(marked,question["correctness"]) for x in pair]
        else:
          template = [x for pair in zip(['']*len(question["correctness"]),question["correctness"]) for x in pair]
        question["answersStr"] = tableTemplate % tuple( template )
        question["questionHTML"] = questionTemplate % question
      elif result['answer_type'] == 'matrix_sort_answer':
        answerList = []
        questionList = []
        question["answers"] = []

        for ai, (t0,t1) in enumerate( zip(result['answers'], result['correct']) ):
          question["answers"].append( ( t1, t0 ) )
          answerList.append( matrixSort_answers_single % { "answerPos_0": ai, "answer": t1 } )
          questionList.append( matrixSort_question_single % { "answerPos_0": ai, "answer": t0 } )

        qaSet = { "ms_questions": "".join( quest for quest in answerList ), "ms_questionsSet": questionList, "ms_answers": "".join( quest for quest in questionList ), "ms_answersSet": answerList }
        question = dict( dict( qaSet.items() + question.items() ) )

        # Populate the question dict with the answers provided
        question["answerType"] = result['answer_type']
        question["numQuestions"] = 0
        # answerStr | correctness
        question["correctness"] = range( len( answerList ) )
        question["numAnswers"] = len( answerList )
        question["json"] = htmlToJson( question )
        question["questionHTML"] = matrixSort_questionTemplate % question
      else:
        print( "Question type not recognised: " + result['answer_type'] + " !" )
        sys.exit(1)

      jsons[str( question["id"] )] = question["json"]
      questions.append( question["questionHTML"] )

    quiz = dict( \
      quizTitle = title,
      questions = '\n'.join( questions ),
      answersJSON = jsons )

    if separateFilenames:
      qfile = filename[:-5] + "_Q" + str(rU[-1]['number']) + ".html"
      Qfilenames.append(qfile)
      with open(qfile, 'w') as outfile:
        outfile.write(quizTemplate % quiz)
    else:
      if len(resultPartition) != 1:
        sys.error("Bizarre")
      with open(filename[:-5] + ".html", 'w') as outfile:
        outfile.write(quizTemplate % quiz)

  return Qfilenames

def toJson(filename, results, title, url, uid):
  with open(filename[:-5] + ".json", 'w') as outfile:
    json.dump(
      {
        "questions" : sorted(results, key=lambda x: x['number']),
        "title" : title,
        "url" : url,
        "uid" : uid
      },
      outfile,
      sort_keys=True,
      indent=2,
      separators=(',', ': ')
    )

#
# update filename in index.html
#
def updateIndex(dirname, jsonPath):
  # prepare JSON filename i.e. remove directories just leave filename
  jsonName = None
  jsonName_i = jsonPath[::-1].find('/')
  if jsonName_i == -1:
    jsonName = jsonPath
  else:
    jsonName =jsonPath[::-1][:jsonName_i][::-1]

  with open(dirname + "index.html", 'w') as writer:
    with open(dirname + "resources/index.html", 'r') as reader:
      for line in reader:
        writer.write(line.replace("my_quiz.json", jsonName))

#
# generate feedback for given user
#
def toFeedback( rootDir, uid, results, sectionCoverage, difficulty ):
  d = []
  for r in results:
    d.append('#' + str(r['number']).zfill(2) + ': ' + r['text'])
  d.sort()

  feedbackFile = rootDir + "feedback_" + '_'.join(uid) + ".txt"
  with open(feedbackFile, 'w') as ffile:
    ffile.write( quizStats(uid, len(results), sectionCoverage, difficulty) )
    ffile.write('\n\n')
    ffile.write( '\n'.join(d) )

#
# generate marked questions
#
def extract(rootDir, uid, results):
  needed_images = []

  any_to_extract = False

  d = [ 'uid: ' + i + '\n' for i in uid]
  for r in results:
    if r['quality']:
      any_to_extract = True
      d.append(r['fullq'])
      # get list of images
      if r['images']:
        if r['images'] not in needed_images:
          needed_images += r['images']

  extractFile = rootDir + "extract_" + '_'.join(uid) + ".quiz"

  if any_to_extract:
    with open(extractFile, 'w') as efile:
      efile.write( '\n'.join(d) )

  return needed_images

#
# generate iFrame
#
def writeIframe(filename, questionFilenames):
  frames = ""
  for f in questionFilenames:
    frames += iframeIframeTemplate % {'filename':f, 'filename':f}
  with open(filename[:-5] + "_iFrame.html", 'w') as if_file:
    if_file.write(iframeGeneralTemplate % {'iframes':frames})

#
# order questions
#
def orderQuestions(filename, order, uid, questions, to_file):
  # TODO: add title and url
  if order == 'O':
    of = '^'
    out = sorted(questions, key=lambda elem: "%d %02d.%02d" % (int(elem['difficulty']), elem['chapter'], elem['section']))
  elif order == 'o':
    of = 'v'
    out = sorted(questions, key=lambda elem: "%02d.%02d %d" % (elem['chapter'], elem['section'], int(elem['difficulty'])))
  else:
    sys.exit('Unknown order')

  if to_file:
    f_content = []
    f_content.append('{\n')
    f_content.append('"candidate_number": ' + json.dumps(uid) + ',\n')
    for i in out:
      f_content.append('\n"' + str(i["number"]) + '": ' + i['fullq'] + ",")
    f_content[-1] = f_content[-1][:-1] # remove the last comma
    f_content.append('\n}\n')
    with open(filename[:-5] + "_" + of + order + ".quiz", 'w') as o_file:
      o_file.write("".join(f_content))

  return out

#
# produce quiz statistics#
#
def quizStats(uid, questionCount, sectionCoverage, difficulty):
  stats =("-----------------------------|\n" +\
          "^ hard:             %2d (%2d%%) |\n" +\
          "| hard-medium:      %2d (%2d%%) |\n" +\
          "| medium:           %2d (%2d%%) |\n" +\
          "| medium-easy:      %2d (%2d%%) |\n" +\
          "v easy:             %2d (%2d%%) |\n" +\
          "-----------------------------|\n" +\
          "~ total:            %2d       |\n" +\
          "-----------------------------|\n" +\
          "@ section coverage: %2d       |\n" +\
          "-----------------------------|\n" ) %\
          (difficulty[0], 100.0*difficulty[0]/questionCount, \
          difficulty[1], 100.0*difficulty[1]/questionCount, \
          difficulty[2], 100.0*difficulty[2]/questionCount, \
          difficulty[3], 100.0*difficulty[3]/questionCount, \
          difficulty[4], 100.0*difficulty[4]/questionCount, \
          questionCount, sectionCoverage)

  difficultyRequirements = "\n"

  authors = ' & '.join(uid)
  authorsNo = len(uid)

  if authorsNo == 2:
    if questionCount < 50: difficultyRequirements += "& too little questions &"
    if sectionCoverage < 25: difficultyRequirements += "& too few sections &"
  elif authorsNo == 1:
    if questionCount < 30: difficultyRequirements += "& too little questions &"
    if sectionCoverage < 15: difficultyRequirements += "& too few sections &"
  else:
    print "Too many candidate numbers detected (", authorsNo, ") : ", authors
    sys.exit(1)

  if 100.0*difficulty[2]/questionCount > 40: difficultyRequirements += "& too many easy &"
  if 100.0*difficulty[0]/questionCount < 20: difficultyRequirements += "& too few hard &"

  detection = "\n"
  if difficultyRequirements != "\n":
    detection += "Detected " + str(authorsNo)
    if authorsNo == 1:
      detection += " author: "
    else:
      detection += " authors: "
    detection += str(authors) + "\nDifficulty requirements broken:" +\
      difficultyRequirements

  return stats + detection

if __name__ == '__main__':
  # parse arguments
  args = parser.parse_args()
  ANSWERS_DEBUG = args.debug
  SHOW_HINTS = args.hints
  SHOW_COMMENTS = args.comments
  SHOW_SOURCE = args.source
  SHOW_WORKINGS = args.workings
  SHOW_EXPLANATION = args.explanation
  quizFilename = args.filename[0]
  # check if given file exists
  if os.path.exists(quizFilename):
    if os.path.isfile(quizFilename):
      if quizFilename[-5:] != ".quiz":
        print("Your file must have `.quiz` extension")
        sys.exit(1)
    elif args.peter or args.Peter:
      pass
    else:
      print(quizFilename + " is not a file!")
      sys.exit(1)
  else:
    print(quizFilename + " does not exist!")
    sys.exit(1)
  # check if the file is located in the root of the repository
  rootDir_i = quizFilename[::-1].find('/')
  if args.peter or args.Peter:
    if quizFilename[-1] == '/':
      rootDir = quizFilename
    else:
      rootDir = quizFilename + '/'
  elif rootDir_i != -1:
    rootDir = quizFilename[::-1][rootDir_i:][::-1]
  else:
    rootDir = "./"
  if (not args.peter) and (not args.Peter):
    if not os.path.exists(rootDir+"resources/js/wpProQuiz_jquery.ui.touch-punch.min.js"):
      print "Your .quiz files must be located in the root directory of this package to work properly."
      sys.exit(1)

  # small p - based on big O ordering
  if args.peter:
    print "Entering Peter's special mode #1"
    quiz_archives = [i for i in os.listdir(rootDir) if '.tar.gz' in i.lower()]
    os.makedirs(rootDir+'special')
    for i in quiz_archives:
      with tarfile.open(i, mode='r:gz') as f:
        f.extractall(path=rootDir+'special')

    # iframe
    quizs = [i for i in os.listdir(rootDir+'special') if '.quiz' in i.lower()]
    link = "<a href=\"%s\">%s</a><br>\n"
    body = ""
    for i in quizs:
      results, title, url, uid, sectionCoverage, difficulty = parseQuestions(rootDir+'special/'+i)

      # bog O ordering
      results = orderQuestions(rootDir+'special/'+i, 'O', uid, results, True)

      qfilenames = toHtml(rootDir+'special/'+i, results, title, True)
      new_qfilenames = [os.path.basename(j) for j in qfilenames]

      # write stat file
      stat = quizStats(uid, len(results), sectionCoverage, difficulty)
      with open(rootDir+'special/'+i[:-5]+'.stat', 'w') as stat_file:
        stat_file.write(stat)

      writeIframe(rootDir+'special/'+i, [i[:-5]+'.stat']+new_qfilenames)

      body += link % (os.path.basename(i)[:-5]+'_iFrame.html', os.path.basename(i))

    # general HTML
    body = iframeGeneralTemplate % {'iframes':body}
    with open(rootDir+'special/index.html', 'w') as index_file:
      index_file.write(body)

    sys.exit(0)

  # big P - based on big O ordering
  if args.Peter:
    print "Entering Peter's special mode #2"
    # generate feedback based on O
    if not os.path.exists(rootDir+'feedback'):
      os.makedirs(rootDir+'feedback')
    if not os.path.exists(rootDir+'extract'):
      os.makedirs(rootDir+'extract')
    quizs = [i for i in os.listdir(rootDir) if '_^O.quiz' in i]
    for i in quizs:
      results, title, url, uid, sectionCoverage, difficulty = parseQuestions(rootDir+os.path.basename(i))
      # bog O ordering
      results = orderQuestions(rootDir+i, 'O', uid, results, False)
      toFeedback( rootDir+'feedback/', uid, results, sectionCoverage, difficulty )
      # extract all marked questions with graphics
      imgs = extract(rootDir+'extract/', uid, results)
      for img in imgs:
        if not os.path.exists(os.path.dirname(rootDir+'extract/'+img)):
          os.makedirs(os.path.dirname(rootDir+'extract/'+img))
        shutil.copy(rootDir+img, os.path.dirname(rootDir+'extract/'+img))
    sys.exit(0)

  results, title, url, uid, sectionCoverage, difficulty = parseQuestions(quizFilename)

  # order questions if needed
  if args.tarball:
    # check usernames
    if len(uid) == 1:
      print "Is your UoB candidate number: ", uid[-1], "?"
    elif len(uid) == 2:
      print "Are your UoB candidate numbers: ", " & ".join(uid), "?"
    else:
      print "Too many candidate numbers detected\n", " & ".join(uid)
      sys.exit(1)

    uid_choices = {"yes": True, "y": True, "ye": True, "no": False, "n": False}
    uid_choice = None
    while True:
      print "Is this correct? [y/n]"
      choice = raw_input().lower()
      if choice in uid_choices:
        uid_choice = uid_choices[choice]
        break
      else:
        print "Please respond with 'yes' or 'no' (or 'y' or 'n')."

    if not uid_choice:
      print "\nOperation failed!"
      print "Please put correct id(s) in the `.quiz` file."
      sys.exit(1)

    # generate html copy and rename
    qfilenames = toHtml(quizFilename, results, title, True)
    # generate iframe with filenames
    writeIframe(quizFilename, qfilenames)

    # modify `img` tags
    with open(quizFilename, 'r') as quiz_file:
      with open(quizFilename[:-5]+'_imgCdV', 'w') as quiz_img_r:
        for line in quiz_file:
          quiz_img_r.write(line.replace('img/', 'img/'+'_'.join(uid)+'/'))

    with tarfile.open('_'.join(uid)+".tar.gz", mode='w:gz') as f:
      # generate master copy - 1:1
      for i in qfilenames:
        f.add(i, arcname='1to1/'+'_'.join(uid)+i[1:])
      f.add(quizFilename[:-5]+"_iFrame.html", arcname='1to1/'+'_'.join(uid)+'/'+os.path.basename(quizFilename)[:-5]+"_iFrame.html")
      f.add(quizFilename, arcname='1to1/'+'_'.join(uid)+'/'+os.path.basename(quizFilename))
      f.add(rootDir+'img', arcname='1to1/'+'_'.join(uid)+'/img')

      # copy images into img/uid/*
      f.add(rootDir+'img', arcname='img/'+'_'.join(uid))
      # copy and rename .quiz - alter img paths
      f.add(quizFilename[:-5]+'_imgCdV', arcname='_'.join(uid)+'.quiz')

    os.remove(quizFilename[:-5]+'_imgCdV')
    print "\nPlease submit *", '_'.join(uid)+".tar.gz", "* file"
    sys.exit(0)

  if args.order:
    print "Ordering the questions first on book section then on difficulty"
    results = orderQuestions(quizFilename, 'o', uid, results, True)
  elif args.Order:
    print "Ordering the questions first on difficulty then on book section"
    results = orderQuestions(quizFilename, 'O', uid, results, True)

  if args.feedback:
    print( "Generating feedback for " + ' & '.join(uid) )
    toFeedback( rootDir, uid, results, sectionCoverage, difficulty )
  elif args.question:
    print( "Generating question #" + str(args.question[-1]) )
    toHtml(quizFilename, results, title, args.question)
  elif args.extract:
    # extract marked questions
    print( "Extracting marked questions" )
    extract(rootDir, uid, results)
  elif args.iframe:
    print( "Generating all of the questions in one file (iframe)" )
    qfilenames = toHtml(quizFilename, results, title, True)
    # generate iframe with filenames
    writeIframe(quizFilename, qfilenames)
  elif args.separate:
    print( "Generating all of the questions in separate files" )
    toHtml(quizFilename, results, title, args.separate)
  # must be the last element of if-elif-else
  elif args.all:
    print( "Generating all of the questions" )
    toHtml(quizFilename, results, title, None)
  else:
    print( "I didn't expect to get here..." )
    sys.exit(1)

  if args.count:
    print quizStats(uid, len(results), sectionCoverage, difficulty),
