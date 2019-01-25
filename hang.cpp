#include <map>
#include <algorithm>
#include <vector>
#include <list>
#include <iostream>
#include <fstream>
#include <memory>

using namespace std::string_literals;

// Class definitions

struct prediction {
	static std::vector<std::unique_ptr<prediction>> all;

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

std::vector<std::unique_ptr<prediction>> prediction::all;

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

std::string current_word;
std::vector<std::string> words;
std::vector<cbit> bits;

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
		predictions.push_back(t_ptr.get());
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

const prediction * best_guess() {

}
