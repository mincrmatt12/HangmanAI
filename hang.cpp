#include <map>
#include <algorithm>
#include <cstring>
#include <vector>
#include <list>
#include <iostream>
#include <fstream>
#include <memory>

using namespace std::string_literals;

// Class definitions

struct prediction {
	static std::list<std::unique_ptr<prediction>> all;

	const uint8_t type_id;
	std::list<prediction *> children{};
	float weight = 0;
	bool certain = false, invalid = false;

	prediction(int type) : type_id(type) {}
	
	virtual bool valid_for(const std::string& word) const {return true;}
	virtual bool depends_on(const prediction* other) const {return false;}
	virtual bool congruent(const prediction* other) const {return false;}
	
	void mark_invalid() {
		this->invalid = true;
		this->certain = false;
		for (auto e : children) {
			e->mark_invalid();
		}
	}

	virtual std::string as_string() const {return "Unknown"s;};
	virtual float importance() const {return 1.0f;}

	std::list<prediction *> parents() const {
		std::list<prediction *> dat{};
		for (auto &p : prediction::all) {
			if (!p->congruent(this) && this->depends_on(p.get())) dat.push_back(p.get());
		}
		return dat;
	}

	std::list<prediction *> topmost() {
		auto p_list = parents();
		if (p_list.size() == 0) {
			return {this};
		}
		std::list<prediction *> result{};
		for (auto &a : p_list) {
			result.splice(result.begin(), a->topmost());
		}
		return result;
	}
};

struct cbit {
	bool at_begin;
	std::string content;

	bool operator==(const cbit& other) const {return at_begin == other.at_begin && content == other.content;}
};

#define P_TYPE(x) const static uint8_t type_marker = x
#define P_BC prediction(type_marker)

template<typename T>
bool isa(const prediction *e) {
	return e->type_id == T::type_marker;
}

template<typename T>
const T* asa(const prediction *e) {
	return reinterpret_cast<const T*>(e);
}

std::list<std::unique_ptr<prediction>> prediction::all;

// Prediction definitions

struct contains_prediction : public prediction {
	P_TYPE(2);

	const std::string segment;

	contains_prediction(const std::string& segment) : P_BC,
		segment(segment) {
	}

	bool valid_for(const std::string& word) const override {
		return word.find(segment) != std::string::npos;
	}

	bool depends_on(const prediction* other) const override {
		if (isa<contains_prediction>(other)) {
			return segment.find(asa<contains_prediction>(other)->segment) != std::string::npos;
		}
		return false;
	}

	bool congruent(const prediction* other) const override {
		if (isa<contains_prediction>(other)) {
			return asa<contains_prediction>(other)->segment == segment;
		}
		return false;
	}

	float importance() const override {return 0.1 * segment.size() + 0.1;}
	std::string as_string() const override {return "Word contains "s + segment;}
};

struct not_prediction : public prediction {
	// a guess, certain letters must not be or must be this
	P_TYPE(1);

	const char mal;
	const std::vector<bool> must_be;

	not_prediction(const char mal, const std::vector<bool>& must_be) : P_BC, 
		mal(mal),
		must_be(must_be) {
	}

	bool valid_for(const std::string& word) const override {
		int i = 0;
		return std::all_of(word.begin(), word.end(), [&](char c){
			bool equal_to = must_be[i++];
			if (!equal_to && c == mal) return false;
			if ( equal_to && c != mal) return false;
			return true;
		});
	}

	bool depends_on(const prediction* other) const override {
		if (isa<contains_prediction>(other)) {
			return asa<contains_prediction>(other)->segment.find(mal) != std::string::npos;
		}
		return false;
	}

	bool congruent(const prediction* other) const override {
		if (isa<not_prediction>(other)) {
			const auto* o = asa<not_prediction>(other);
			return o->mal == mal && o->must_be == must_be;
		}
		return false;
	}

	std::string as_string() const override {return "Contains specific letters";}
};

struct uses_bit_prediction : public prediction {
	// uses an ending/prefix
	
	P_TYPE(3);

	const cbit bit;

	uses_bit_prediction(const cbit& bit) : P_BC,
		bit(bit) {
	}

	bool valid_for(const std::string& word) const override {
		if (bit.at_begin) {
			return 0 == word.compare(0, bit.content.size(), bit.content);
		}
		else {
			return 0 == word.compare(word.size() - bit.content.size(), bit.content.size(), bit.content);
		}
	}

	bool depends_on(const prediction* other) const override {
		if (isa<contains_prediction>(other)) {
			return bit.content.find(asa<contains_prediction>(other)->segment) != std::string::npos;
		}
		return false;
	}

	bool congruent(const prediction* other) const override {
		if (isa<uses_bit_prediction>(other)) {
			return asa<uses_bit_prediction>(other)->bit == this->bit;
		}
		return false;
	}

	float importance() const override {
		return 0.125f + 0.075f*this->bit.content.size();
	}

	std::string as_string() const override {
		if (bit.at_begin) {
			return "Word starts with "s + bit.content;
		}
		else {
			return "Word ends with "s + bit.content;
		}
	}
};

struct matches_holemap_prediction : public prediction {
	// matches a holemap:
	//
	// some combination of letter-letter
	
	P_TYPE(4);

	const std::string holemap;

	matches_holemap_prediction(const std::string& holemap) : P_BC,
		holemap(holemap) {
	}

	bool valid_for(const std::string& word) const override {
		return word.size() == holemap.size() && std::equal(word.begin(), word.end(), holemap.begin(), [](auto a, auto b){
				return (b != '-' ? a == b : true);
		});
	}

	bool depends_on(const prediction* other) const override {
		if (isa<matches_holemap_prediction>(other)) {
			const auto* o = asa<matches_holemap_prediction>(other);
			if (std::equal(holemap.begin(), holemap.end(), o->holemap.begin(), [](auto i, auto j){
					return (i == j) || (i == '-') || (j == '-');
			})) {
				return holemap.size() - std::count(holemap.begin(), holemap.end(), '-') <=
					   o->holemap.size() - std::count(o->holemap.begin(), o->holemap.end(), '-');
			}
		}
		else if (isa<contains_prediction>(other)) {
			return holemap.find(asa<contains_prediction>(other)->segment) != std::string::npos;
		}
		return false;
	}

	bool congruent(const prediction *other) const override {
		if (isa<matches_holemap_prediction>(other))
			return holemap == asa<matches_holemap_prediction>(other)->holemap;
		return false;
	}

	float importance() const override {
		return .15f * (holemap.size() - std::count(holemap.begin(), holemap.end(), '-')) + .2f;
	}

	std::string as_string() const override {
		return "Word matches "s + holemap;
	}
};

// loaded file resources

std::vector<std::string> words;
std::vector<cbit> bits;
std::map<std::string, float> word_popularity;

// global state

std::vector<std::string> possible;
std::list<prediction *> predictions;
std::string status;

template<typename T, typename... Args>
prediction * make_prediction(Args&&... args) {
	auto t_ptr = std::make_unique<T>(std::forward<Args>(args)...);
	decltype(prediction::all)::iterator duplicate;
	if ((duplicate = std::find_if(prediction::all.begin(), prediction::all.end(), [&](const auto &p1){
		return p1->congruent(t_ptr.get());
	})) != prediction::all.end()) {
		return duplicate->get();
	}

	if (std::none_of(predictions.begin(), predictions.end(), [&](const auto &p1){
		return t_ptr->depends_on(p1) && p1->invalid;
	})) {
		predictions.push_front(t_ptr.get());
	}

	auto r_ptr = t_ptr.get();

	for (auto& possible_ancestry : prediction::all) {
		if (possible_ancestry->depends_on(r_ptr)) {
			r_ptr->children.push_back(possible_ancestry.get());
		}
		else if (r_ptr->depends_on(possible_ancestry.get())) {
			possible_ancestry->children.push_back(r_ptr);
		}
	}

	prediction::all.emplace_back(std::move(t_ptr));
	return r_ptr;
}

void init_default_predictions() {
	for (char c = 'a'; c <= 'z'; ++c) {
		make_prediction<contains_prediction>(std::string{c});
	}

	for (const auto& b : bits) {
		make_prediction<uses_bit_prediction>(b);
	}
}

// prediction generators

void generate_random_common() {
	const int DEPTH = 2;

	for (const auto& prediction : predictions) {
		if (!prediction->certain && !prediction->invalid) {
			if (isa<contains_prediction>(prediction)) {
				const auto& pcp = asa<contains_prediction>(prediction);
				std::array<int, 26> vals = {0};
				for (const std::string& word : possible) {
					if (prediction->valid_for(word)) {
						for (unsigned int i = 0; i < word.size() - pcp->segment.size(); ++i) {
							if (word.compare(i, pcp->segment.size(), pcp->segment)) {
								for (const auto&c : pcp->segment) {
									vals[c - 'a']++;
								}
							}
						}
					}
				}
				for (int i = 0; i < DEPTH; ++i) {
					auto ptr = std::max_element(vals.begin(), vals.end());
					make_prediction<contains_prediction>(pcp->segment + std::string{static_cast<char>((ptr - vals.begin()) + 'a')});
					*ptr = 0;
				}
			}
		}
	}
}

void generate_current_board() {
	make_prediction<matches_holemap_prediction>(status)->certain = true;
}

void generate_invalid_mask() {
	std::vector<bool> mask{};

	for (char c = 'a'; c <= 'z'; ++c) {
		if (status.find(c) != std::string::npos) {
			mask.clear();
			for (const auto& oc : status) {
				if (oc == c) mask.push_back(true);
				else		 mask.push_back(false);
			}

			make_prediction<not_prediction>(c, mask)->certain = true;
		}
	}
}

void generate_predictions() {
	generate_invalid_mask();
	generate_random_common();
	generate_current_board();
}

prediction * best_guess() {
	// strategy to get guesses:
	//
	// find the highest weighted prediction which is neither certain nor invalid
	// find it's topmost things (which should only be contains)
	// pick the highest weighted one of _those_, and return it
	
	std::list<prediction *> prediction_copy = predictions;

	prediction_copy.remove_if([](const auto& p){return p->certain || p->invalid;});

	while (!prediction_copy.empty()) {
		auto best_choice = std::max_element(prediction_copy.begin(), prediction_copy.end(), [](const auto &a, const auto &b){return a->weight < b->weight;});
		auto topmosts = (*best_choice)->topmost();
		topmosts.remove_if([](const auto& p){return p->certain || p->invalid;});
		if (topmosts.empty()) prediction_copy.erase(best_choice);
		else {
			auto real_best = std::max_element(topmosts.begin(), topmosts.end(), [](const auto &a, const auto &b){return a->weight < b->weight;}); 
			return *real_best;
		}
	}

	throw std::runtime_error("no predictions remaining");
}

// wrangle current predictions

template<bool Second>
void update_predictions_loop(float vals[], std::vector<std::string> &new_possible) {
	int old_size = predictions.size();

    #pragma omp parallel for reduction(+:vals[:old_size])
	for (int i = 0; i < possible.size(); ++i) {
		// collapse ommited here because i want things
		bool good = true;
		int j = 0;
		for (const auto &a : predictions) {
			if (a->valid_for(possible[i])) {
				if (a->invalid) {
					good = false;
				}
				if constexpr (Second)
					vals[j] += word_popularity[possible[i]] * a->importance();
			}
			else if (a->certain) {
				good = false;
			}
			++j;
		}

		if constexpr (!Second) {
			if (good) {
			#pragma omp critical(new_possible_inc)
				{
					new_possible.push_back(possible[i]);
				}
			}
		}
		
		if (i % 150 == 0) {
			#pragma omp critical(cout)
			{
				std::cout << (Second ? "WVC2: " : "WVC: ") << i << " of " << possible.size() << "\r";
			}
		}
	}
	std::cout << (Second ? "WCV2: " : "WVC: ") << possible.size() << " of " << possible.size() << "\r";
	std::cout << std::endl;
}

void update_predictions() {
	// check for forced valididity/invalidity
	//
	// if a prediction is good for the current status, mark it as certain
	
	{
		int j = 0;
		for (auto &i : predictions) {
			if (!(i->certain || i->invalid)) {
				if (i->valid_for(status)) {
					i->certain = true;
					i->invalid = false;
				}
				else if (!possible.empty()) {
					auto tops = i->topmost();
					if (std::all_of(tops.begin(), tops.end(), [](const auto& p){return p->certain && !p->invalid;})) {
						i->invalid = true;
						i->certain = false;
					}
				}
			}
			if (j % 8 == 0)
				std::cout << "FVC: " << j << " of " << predictions.size() << "\r";
			++j;
		}
		std::cout << std::endl;
	}

	// the primary loop: investigate which words are valid, as well as assign vals
	float vals[predictions.size()];
	memset(vals, 0, predictions.size() * sizeof(float));
	std::vector<std::string> new_possible{};

	update_predictions_loop<false>(vals, new_possible);
	// we now have the possible array, so let's copy that
	possible = std::move(new_possible);

	// redo it to get properly setup vals
	update_predictions_loop<true>(vals, new_possible);

	// now, we can go weight all of the predictions
	
	{
		int j = 0;
		for (auto& i: predictions) {
			i->weight = (vals[j] / (float)possible.size()) * i->importance();
			++j;
			std::cout << "PW: " << j << " of " << predictions.size() << "\r";
		}
		std::cout << std::endl;
	}

	// finally, we can prune everything with a weight of zero
	
	predictions.remove_if([](const auto &c){
		return c->weight == 0.0f;
	});
}

void init_file_data() {
	std::ifstream word_list("words.txt");

	char line[64] = {0}; // some words are fairly long

	while (word_list.getline(line, 64)) {
		std::string l = line;
		
		if (l.find('-') != std::string::npos) continue;
		words.push_back(std::move(l));
	}

	std::ifstream bit_list("common_bits.txt");
	
	while (word_list.getline(line, 64)) {
		cbit c;
		c.content = std::string{line + 1};
		c.at_begin = *line == '+';

		bits.push_back(std::move(c));
	}

	std::ifstream pop_list("word_counts.txt");
	float minimum_pop = std::numeric_limits<float>::max();

	while (pop_list) {
		std::string word;
		float pop;

		pop_list >> word;
		pop_list >> pop;

		word_popularity[word] = pop;
		minimum_pop = std::min(pop, minimum_pop);
	}

	for (const auto& word : words) {
		if (word_popularity.count(word) == 0) word_popularity[word] = minimum_pop;
	}
}

void init(int length) {
	init_file_data();
	init_default_predictions();

	status = std::string(length, '-');
	
	for (const auto& word : words) {
		if (word.size() == length) possible.push_back(word);
	}
}

int main(int argc, char ** argv) {
	std::cout << "HangmanAI v2.0" << std::endl
		      << "Copyright (c) Matthew Mirvish 2019" << std::endl
			  << "See LICENSE for more information" << std::endl << std::endl;
	// Begin by asking for the length of the word.
	
	int word_length;
	std::cout << "How many dashes? " << std::endl;
	std::cin >> word_length;
	std::cin.ignore(std::numeric_limits<std::streamsize>::max(), '\n');

	std::cout << "protip: you can enter nothing at the 'new state' prompt for a wrong guess!" << std::endl;
	std::cout << "Loading with length " << word_length << "...";
	std::cout.flush();
	init(word_length);
	std::cout << "done." << std::endl;

	// Main game loop -- update, get guess, display state, ask for new status, repeat
	
	int total_guesses = 0, wrong_guesses = 0;
	
	while (status.find('-') != std::string::npos) {
		generate_predictions();
		update_predictions();
		auto guess = best_guess();

		total_guesses += 1;

		if (!isa<contains_prediction>(guess)) throw std::logic_error("invalid prediction type in loop");
		std::cout << "== " << status << " ==" << std::endl;
		std::cout << "== GUESS: " << asa<contains_prediction>(guess)->segment << " ==";
		std::cout << std::endl << std::endl;
		std::cout << "What is the new state of the game? " << std::endl;
		std::cout.flush();

		std::string new_status;
retry:
		std::getline(std::cin, new_status);

		if (new_status.size() != 0 && new_status.size() != word_length) {
			std::cout << "That's not the right length!" << std::endl;
			goto retry;
		}

		if (new_status != status) {
			for (int i = 0; i < word_length; ++i) {
				if (status[i] != '-' && new_status[i] != status[i]) {
					std::cout << "You changed a letter!" << std::endl;
					goto retry;
				}
			}
		}

		if (new_status == status || new_status.size() == 0) {
			std::cout << "Wrong guess!" << std::endl;

			guess->mark_invalid();
			wrong_guesses += 1;
		}
		else {
			std::cout << "Excellent!" << std::endl;
			guess->certain = true;
		}

		if (new_status.size() != 0) status = new_status;

		if (possible.size() == 0) {
			throw std::runtime_error("no more words");
		}
	}

	std::cout << "Word is: " << status << std::endl;
	std::cout << "Total guesses: " << total_guesses << std::endl
		      << "Wrong guesses: " << wrong_guesses << std::endl;
	return 0;
}
